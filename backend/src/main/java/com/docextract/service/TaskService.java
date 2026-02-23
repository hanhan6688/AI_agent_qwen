package com.docextract.service;

import com.docextract.config.QwenConfig;
import com.docextract.dto.TaskDTO;
import com.docextract.dto.TaskProgressDTO;
import com.docextract.entity.Task;
import com.docextract.entity.User;
import com.docextract.repository.TaskRepository;
import com.docextract.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.web.multipart.MultipartFile;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.LocalDateTime;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import java.util.stream.Collectors;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

@Service
@RequiredArgsConstructor
@Slf4j
public class TaskService {

    private final TaskRepository taskRepository;
    private final UserRepository userRepository;
    private final QwenExtractService qwenExtractService;
    private final QwenConfig qwenConfig;

    @Value("${file.upload-dir:./data/uploads}")
    private String uploadDir;

    @Value("${file.output-dir:./data/outputs}")
    private String outputDir;

    @Value("${file.data-dir:./data}")
    private String dataDir;

    /**
     * 创建批量提取任务
     */
    @Transactional
    public List<TaskDTO> createTasks(Long userId, String taskName, String extractFieldsJson, String modelMode, MultipartFile[] files) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new RuntimeException("用户不存在"));

        List<Task> createdTasks = new ArrayList<>();

        // 创建任务目录结构: data/taskName/{pdf, json_data, result}
        Path taskPdfDir = Paths.get(dataDir, sanitizeTaskName(taskName), "pdf");
        Path taskJsonDir = Paths.get(dataDir, sanitizeTaskName(taskName), "json_data");
        
        try {
            Files.createDirectories(taskPdfDir);
            Files.createDirectories(taskJsonDir);
            log.info("创建任务目录: pdf={}, json_data={}", taskPdfDir, taskJsonDir);
        } catch (IOException e) {
            throw new RuntimeException("创建任务目录失败: " + e.getMessage());
        }

        for (MultipartFile file : files) {
            if (file.isEmpty()) continue;

            try {
                // 生成唯一文件名
                String originalFilename = file.getOriginalFilename();
                String fileExtension = originalFilename.substring(originalFilename.lastIndexOf("."));
                String uniqueFileName = UUID.randomUUID().toString() + fileExtension;

                // 保存文件到任务目录下的pdf文件夹
                Path filePath = taskPdfDir.resolve(uniqueFileName);
                file.transferTo(filePath.toFile());

                // 创建任务 - 使用用户自定义的任务名称
                Task task = Task.builder()
                        .user(user)
                        .taskName(taskName)
                        .documentCount(1)
                        .filePath(Map.of(
                            "fileName", originalFilename, 
                            "filePath", uniqueFileName,
                            "taskDataDir", Paths.get(dataDir, sanitizeTaskName(taskName)).toString()
                        ))
                        .status(Task.TaskStatus.PENDING)
                        .stage("PENDING")
                        .progress(0)
                        .retryCount(0)
                        .startTime(LocalDateTime.now())
                        .build();

                task = taskRepository.save(task);
                createdTasks.add(task);

                log.info("任务创建成功: taskId={}, fileName={}, savedTo={}", task.getTaskId(), originalFilename, filePath);

            } catch (IOException e) {
                log.error("文件上传失败: {}", file.getOriginalFilename(), e);
                throw new RuntimeException("文件上传失败: " + file.getOriginalFilename());
            }
        }

        // 更新用户文档数量
        user.setDocumentCount(user.getDocumentCount() + createdTasks.size());
        userRepository.save(user);

        // 提取taskId列表（在事务内完成）
        List<Long> taskIds = createdTasks.stream()
                .map(Task::getTaskId)
                .collect(Collectors.toList());

        // 在事务提交后再启动异步处理
        String finalModelMode = modelMode;
        TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
            @Override
            public void afterCommit() {
                log.info("事务已提交，开始异步处理任务: {}, modelMode={}", taskIds, finalModelMode);
                processTasksBatchAsync(taskIds, extractFieldsJson, finalModelMode);
            }
        });

        return createdTasks.stream()
                .map(this::convertToDTO)
                .collect(Collectors.toList());
    }

    /**
     * 异步批量处理任务
     */
    @Async("taskExecutor")
    public void processTasksBatchAsync(List<Long> taskIds, String extractFieldsJson, String modelMode) {
        log.info("开始批量处理任务: {} 个, modelMode={}", taskIds.size(), modelMode);

        // 使用CompletableFuture进行并行处理
        List<CompletableFuture<Void>> futures = taskIds.stream()
                .map(taskId -> CompletableFuture.runAsync(() -> processSingleTask(taskId, extractFieldsJson, modelMode)))
                .toList();

        // 等待所有任务完成
        CompletableFuture.allOf(futures.toArray(new CompletableFuture[0])).join();

        log.info("批量处理完成");
    }

    /**
     * 处理单个任务
     */
    @Transactional
    public void processSingleTask(Long taskId, String extractFieldsJson, String modelMode) {
        Task task = taskRepository.findById(taskId)
                .orElseThrow(() -> new RuntimeException("任务不存在: " + taskId));

        try {
            task.setStatus(Task.TaskStatus.PROCESSING);
            task.setStage("UPLOADING");
            task.setProgress(5);
            taskRepository.save(task);

            // 调用Qwen提取服务，传递 modelMode
            Map<String, Object> result = qwenExtractService.processTask(task, extractFieldsJson, modelMode);

            // 保存结果
            task.setResult(result);
            task.setStatus(Task.TaskStatus.COMPLETED);
            task.setStage("COMPLETED");
            task.setProgress(100);
            task.setEndTime(LocalDateTime.now());

            // 添加处理详情
            Map<String, Object> details = new HashMap<>();
            details.put("model", result.getOrDefault("model", "unknown"));
            details.put("modelMode", modelMode);
            details.put("confidence", result.getOrDefault("confidence", 0.0));
            details.put("processedAt", LocalDateTime.now().toString());
            task.setProcessingDetails(details);

            taskRepository.save(task);

            log.info("任务处理完成: taskId={}, model={}", task.getTaskId(), details.get("model"));

        } catch (Exception e) {
            log.error("任务处理失败: taskId={}", task.getTaskId(), e);

            task.setStatus(Task.TaskStatus.FAILED);
            task.setStage("FAILED");
            task.setEndTime(LocalDateTime.now());
            task.setErrorMessage(e.getMessage());
            task.setRetryCount(task.getRetryCount() + 1);

            taskRepository.save(task);
        }
    }

    /**
     * 重试失败的任务
     */
    @Transactional
    public TaskDTO retryTask(Long taskId, String extractFieldsJson) {
        Task task = taskRepository.findById(taskId)
                .orElseThrow(() -> new RuntimeException("任务不存在"));

        if (task.getStatus() != Task.TaskStatus.FAILED) {
            throw new RuntimeException("只能重试失败的任务");
        }

        if (task.getRetryCount() >= qwenConfig.getMaxRetries()) {
            throw new RuntimeException("已达到最大重试次数");
        }

        task.setStatus(Task.TaskStatus.PENDING);
        task.setStage("PENDING");
        task.setProgress(0);
        task.setErrorMessage(null);
        task.setStartTime(LocalDateTime.now());
        taskRepository.save(task);

        // 异步处理 - 重试时使用普通版模式
        processSingleTask(taskId, extractFieldsJson, "normal");

        return convertToDTO(task);
    }

    /**
     * 获取任务进度
     */
    public TaskProgressDTO getTaskProgress(Long taskId) {
        TaskProgressDTO cachedProgress = qwenExtractService.getProgress(taskId);
        if (cachedProgress != null) {
            return cachedProgress;
        }

        // 如果缓存中没有，从数据库获取
        Task task = taskRepository.findById(taskId)
                .orElseThrow(() -> new RuntimeException("任务不存在"));

        return TaskProgressDTO.builder()
                .taskId(taskId)
                .stage(task.getStage())
                .stageText(getStageText(task.getStage()))
                .progress(task.getProgress() != null ? task.getProgress() : 0)
                .errorMessage(task.getErrorMessage())
                .build();
    }

    /**
     * 分页获取用户任务
     */
    public Page<TaskDTO> getTasksByUserId(Long userId, int page, int size) {
        Sort sort = Sort.by(Sort.Direction.DESC, "createdAt");
        Pageable pageable = PageRequest.of(page, size, sort);
        Page<Task> tasks = taskRepository.findByUserUserIdOrderByCreatedAtDesc(userId, pageable);
        return tasks.map(this::convertToDTO);
    }

    /**
     * 获取任务详情
     */
    public TaskDTO getTaskById(Long taskId) {
        Task task = taskRepository.findById(taskId)
                .orElseThrow(() -> new RuntimeException("任务不存在"));
        return convertToDTO(task);
    }

    /**
     * 获取任务状态
     */
    public String getTaskStatus(Long taskId) {
        Task task = taskRepository.findById(taskId)
                .orElseThrow(() -> new RuntimeException("任务不存在"));
        return task.getStatus().name();
    }

    /**
     * 获取用户活跃任务数
     */
    public long getActiveTaskCount(Long userId) {
        return taskRepository.countByUserUserIdAndStatusIn(userId,
                List.of(Task.TaskStatus.PENDING, Task.TaskStatus.PROCESSING));
    }

    /**
     * 删除任务
     */
    @Transactional
    public void deleteTask(Long taskId) {
        Task task = taskRepository.findById(taskId)
                .orElseThrow(() -> new RuntimeException("任务不存在"));

        // 删除关联文件
        try {
            if (task.getFilePath() != null) {
                String filePath = task.getFilePath().get("filePath");
                if (filePath != null) {
                    Path path = Paths.get(uploadDir, filePath);
                    Files.deleteIfExists(path);
                }
            }
        } catch (IOException e) {
            log.error("删除文件失败: {}", e.getMessage());
        }

        taskRepository.delete(task);
    }

    /**
     * 转换为DTO
     */
    private TaskDTO convertToDTO(Task task) {
        return TaskDTO.builder()
                .taskId(task.getTaskId())
                .userId(task.getUser().getUserId())
                .username(task.getUser().getUsername())
                .taskName(task.getTaskName())
                .documentCount(task.getDocumentCount())
                .filePath(task.getFilePath())
                .status(task.getStatus().name())
                .statusText(getStatusText(task.getStatus()))
                .stage(task.getStage())
                .progress(task.getProgress())
                .retryCount(task.getRetryCount())
                .startTime(task.getStartTime())
                .endTime(task.getEndTime())
                .result(task.getResult())
                .extractFields(task.getExtractFields())
                .processingDetails(task.getProcessingDetails())
                .errorMessage(task.getErrorMessage())
                .createdAt(task.getCreatedAt())
                .updatedAt(task.getUpdatedAt())
                .build();
    }

    private String getStatusText(Task.TaskStatus status) {
        return switch (status) {
            case PENDING -> "等待处理";
            case PROCESSING -> "处理中";
            case COMPLETED -> "已完成";
            case FAILED -> "失败";
        };
    }

    private String getStageText(String stage) {
        if (stage == null) return "未知";
        return switch (stage) {
            case "PENDING" -> "等待处理";
            case "UPLOADING" -> "上传文件中";
            case "OCR_PROCESSING" -> "OCR识别中";
            case "QWEN_EXTRACTING" -> "AI提取中";
            case "COMPLETED" -> "处理完成";
            case "FAILED" -> "处理失败";
            default -> "处理中";
        };
    }

    /**
     * 清理任务名称，移除不安全的字符
     */
    private String sanitizeTaskName(String taskName) {
        if (taskName == null) return "unnamed";
        // 只保留字母、数字、中文、下划线和短横线
        return taskName.replaceAll("[^a-zA-Z0-9\\u4e00-\\u9fa5_-]", "_");
    }

    /**
     * 获取任务的数据目录路径
     */
    public String getTaskDataDir(String taskName) {
        return Paths.get(dataDir, sanitizeTaskName(taskName)).toString();
    }

    /**
     * 获取任务result目录路径
     */
    public String getTaskResultDir(String taskName) {
        return Paths.get(dataDir, sanitizeTaskName(taskName), "result").toString();
    }

    /**
     * 获取JSON zip文件路径
     */
    public String getJsonZipPath(String taskName) {
        return Paths.get(dataDir, sanitizeTaskName(taskName), "result", sanitizeTaskName(taskName) + ".zip").toString();
    }

    /**
     * 将json_data目录下的JSON文件打包成zip保存到result目录
     */
    public String createJsonZip(String taskName) {
        String safeTaskName = sanitizeTaskName(taskName);
        Path jsonDir = Paths.get(dataDir, safeTaskName, "json_data");
        Path resultDir = Paths.get(dataDir, safeTaskName, "result");
        Path zipPath = resultDir.resolve(safeTaskName + ".zip");

        log.info("打包JSON文件: jsonDir={}, zipPath={}", jsonDir, zipPath);

        if (!Files.exists(jsonDir)) {
            throw new RuntimeException("JSON数据目录不存在");
        }

        File[] jsonFiles = jsonDir.toFile().listFiles((dir, name) -> name.endsWith(".json"));
        if (jsonFiles == null || jsonFiles.length == 0) {
            throw new RuntimeException("没有找到JSON文件");
        }

        try {
            // 创建result目录
            Files.createDirectories(resultDir);

            // 打包成zip
            try (ZipOutputStream zos = new ZipOutputStream(new FileOutputStream(zipPath.toFile()))) {
                for (File jsonFile : jsonFiles) {
                    ZipEntry entry = new ZipEntry(jsonFile.getName());
                    zos.putNextEntry(entry);
                    Files.copy(jsonFile.toPath(), zos);
                    zos.closeEntry();
                }
            }

            log.info("JSON zip文件已生成: {}", zipPath);
            return zipPath.toString();

        } catch (IOException e) {
            log.error("打包JSON文件失败: {}", e.getMessage());
            throw new RuntimeException("打包失败: " + e.getMessage());
        }
    }

    /**
     * 按任务名称获取所有子任务
     */
    public List<TaskDTO> getTasksByTaskName(Long userId, String taskName) {
        List<Task> tasks = taskRepository.findByUserIdAndTaskName(userId, taskName);
        return tasks.stream()
                .map(this::convertToDTO)
                .collect(Collectors.toList());
    }

    /**
     * 获取用户所有批量任务（按taskName分组）
     */
    public List<Map<String, Object>> getBatchTasks(Long userId) {
        // 获取所有任务
        List<Task> allTasks = taskRepository.findByUserUserIdOrderByCreatedAtDesc(userId);

        // 按taskName分组
        Map<String, List<Task>> groupedTasks = allTasks.stream()
                .collect(Collectors.groupingBy(Task::getTaskName, LinkedHashMap::new, Collectors.toList()));

        List<Map<String, Object>> batchTasks = new ArrayList<>();
        for (Map.Entry<String, List<Task>> entry : groupedTasks.entrySet()) {
            String taskName = entry.getKey();
            List<Task> tasks = entry.getValue();

            // 计算整体状态
            int completed = 0, processing = 0, failed = 0, pending = 0;
            for (Task t : tasks) {
                switch (t.getStatus()) {
                    case COMPLETED -> completed++;
                    case PROCESSING -> processing++;
                    case FAILED -> failed++;
                    case PENDING -> pending++;
                }
            }

            String overallStatus;
            if (failed > 0 && completed + failed == tasks.size()) {
                overallStatus = "FAILED";
            } else if (processing > 0 || pending > 0) {
                overallStatus = "PROCESSING";
            } else if (completed == tasks.size()) {
                overallStatus = "COMPLETED";
            } else {
                overallStatus = "PENDING";
            }

            // 获取创建时间（最早的）
            LocalDateTime createdAt = tasks.stream()
                    .map(Task::getCreatedAt)
                    .filter(Objects::nonNull)
                    .min(LocalDateTime::compareTo)
                    .orElse(null);

            Map<String, Object> batchTask = new LinkedHashMap<>();
            batchTask.put("taskName", taskName);
            batchTask.put("totalCount", tasks.size());
            batchTask.put("completedCount", completed);
            batchTask.put("processingCount", processing);
            batchTask.put("failedCount", failed);
            batchTask.put("pendingCount", pending);
            batchTask.put("status", overallStatus);
            batchTask.put("createdAt", createdAt);
            batchTask.put("taskIds", tasks.stream().map(Task::getTaskId).collect(Collectors.toList()));
            batchTask.put("files", tasks.stream().map(t -> {
                Map<String, Object> file = new LinkedHashMap<>();
                file.put("taskId", t.getTaskId());
                file.put("fileName", t.getFilePath() != null ? t.getFilePath().get("fileName") : "-");
                file.put("filePath", t.getFilePath() != null ? t.getFilePath().get("filePath") : null);
                file.put("status", t.getStatus().name());
                file.put("progress", t.getProgress());
                file.put("stage", t.getStage());
                file.put("errorMessage", t.getErrorMessage());
                return file;
            }).collect(Collectors.toList()));

            batchTasks.add(batchTask);
        }

        // 按创建时间倒序排列
        batchTasks.sort((a, b) -> {
            LocalDateTime timeA = (LocalDateTime) a.get("createdAt");
            LocalDateTime timeB = (LocalDateTime) b.get("createdAt");
            if (timeA == null && timeB == null) return 0;
            if (timeA == null) return 1;
            if (timeB == null) return -1;
            return timeB.compareTo(timeA);
        });

        return batchTasks;
    }

    /**
     * 删除批量任务（删除该taskName下的所有任务）
     */
    @Transactional
    public void deleteBatchTask(Long userId, String taskName) {
        List<Task> tasks = taskRepository.findByUserIdAndTaskName(userId, taskName);
        for (Task task : tasks) {
            // 删除关联文件
            try {
                if (task.getFilePath() != null) {
                    String filePath = task.getFilePath().get("filePath");
                    if (filePath != null) {
                        Path path = Paths.get(uploadDir, filePath);
                        Files.deleteIfExists(path);
                    }
                }
            } catch (IOException e) {
                log.error("删除文件失败: {}", e.getMessage());
            }
            taskRepository.delete(task);
        }
    }
}
