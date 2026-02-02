package com.docextract.service;

import com.docextract.dto.TaskCreateRequest;
import com.docextract.dto.TaskResponse;
import com.docextract.entity.Task;
import com.docextract.entity.Task.TaskStatus;
import com.docextract.repository.TaskRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Slf4j
@Service
@RequiredArgsConstructor
public class TaskService {

    private final TaskRepository taskRepository;
    private final FileStorageService fileStorageService;
    private final RedisQueueService redisQueueService;

    @Value("${app.storage.upload-path}")
    private String uploadPath;

    public List<TaskResponse> createBatchTasks(TaskCreateRequest request, List<MultipartFile> files) throws Exception {
        log.info("批量创建任务: {}，文件数量: {}", request.getTaskName(), files.size());

        List<TaskResponse> responses = new ArrayList<>();
        String batchId = generateBatchId();

        for (MultipartFile file : files) {
            try {
                // 保存文件
                String filePath = fileStorageService.storeFile(file);

                // 生成任务ID：时间戳+UUID
                String taskId = generateTaskId();

                // 创建任务记录
                Task task = Task.builder()
                        .taskId(taskId)
                        .userId(request.getUserId())
                        .taskName(request.getTaskName() + " - " + file.getOriginalFilename())
                        .status(TaskStatus.PENDING)
                        .filePath(filePath)
                        .fileName(file.getOriginalFilename())
                        .fileSize(file.getSize())
                        .pdfCount(1)  // 单个任务处理一个PDF文件
                        .extractFields(request.getExtractFields())
                        .priority(5)
                        .batchId(batchId)
                        .createdAt(LocalDateTime.now())
                        .build();

                task = taskRepository.save(task);

                // 将任务加入Redis队列
                redisQueueService.addToPendingQueue(task.getTaskId());

                log.info("任务创建成功: {}", task.getTaskId());
                responses.add(TaskResponse.fromEntity(task));

            } catch (Exception e) {
                log.error("创建任务失败 - 文件: {}", file.getOriginalFilename(), e);
                // 继续处理其他文件
            }
        }

        return responses;
    }

    private String generateTaskId() {
        String timestamp = DateTimeFormatter.ofPattern("yyyyMMddHHmmss").format(LocalDateTime.now());
        String uuid = UUID.randomUUID().toString().replace("-", "").substring(0, 8);
        return timestamp + "-" + uuid;
    }

    private String generateBatchId() {
        return "BATCH-" + System.currentTimeMillis();
    }

    public Optional<Task> getTaskById(String taskId) {
        return taskRepository.findById(taskId);
    }

    public Page<TaskResponse> getUserTasks(Long userId, int page, int size) {
        Pageable pageable = PageRequest.of(page, size, Sort.by(Sort.Direction.DESC, "createdAt"));
        Page<Task> tasks = taskRepository.findByUserIdOrderByCreatedAtDesc(userId, pageable);
        return tasks.map(TaskResponse::fromEntity);
    }

    public TaskResponse updateTaskStatus(String taskId, TaskStatus status) {
        Task task = taskRepository.findById(taskId)
                .orElseThrow(() -> new RuntimeException("任务不存在"));

        task.setStatus(status);

        if (status == TaskStatus.PROCESSING && task.getStartedAt() == null) {
            task.setStartedAt(LocalDateTime.now());
        } else if (status == TaskStatus.COMPLETED || status == TaskStatus.FAILED) {
            task.setCompletedAt(LocalDateTime.now());
        }

        task = taskRepository.save(task);
        return TaskResponse.fromEntity(task);
    }

    public TaskResponse updateTaskError(String taskId, String errorMessage) {
        Task task = taskRepository.findById(taskId)
                .orElseThrow(() -> new RuntimeException("任务不存在"));

        task.setStatus(TaskStatus.FAILED);
        task.setErrorMessage(errorMessage);
        task.setCompletedAt(LocalDateTime.now());

        task = taskRepository.save(task);
        return TaskResponse.fromEntity(task);
    }

    public TaskResponse updateTaskExcelPath(String taskId, String excelPath) {
        Task task = taskRepository.findById(taskId)
                .orElseThrow(() -> new RuntimeException("任务不存在"));

        task.setExcelPath(excelPath);
        task.setStatus(TaskStatus.COMPLETED);
        task.setCompletedAt(LocalDateTime.now());

        task = taskRepository.save(task);
        return TaskResponse.fromEntity(task);
    }

    public void deleteTask(String taskId) {
        log.info("删除任务: {}", taskId);
        taskRepository.deleteById(taskId);
    }

    public List<Task> getPendingTasks() {
        return taskRepository.findByStatus(TaskStatus.PENDING);
    }

    public long getTaskCount(Long userId, TaskStatus status) {
        return taskRepository.countByUserIdAndStatus(userId, status);
    }

    public List<Task> getTasksByBatchId(String batchId) {
        return taskRepository.findByBatchId(batchId);
    }
}
