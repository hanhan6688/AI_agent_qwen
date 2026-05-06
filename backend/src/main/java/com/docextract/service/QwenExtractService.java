package com.docextract.service;

import com.docextract.config.QwenConfig;
import com.docextract.dto.TaskProgressDTO;
import com.docextract.entity.Task;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;

import java.io.BufferedReader;
import java.io.File;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import jakarta.annotation.PostConstruct;

/**
 * Qwen智能提取服务 - 优化版
 * 支持进程池管理、进度追踪、重试机制
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class QwenExtractService {

    @Value("${python.worker-dir}")
    private String pythonWorkerDir;

    @Value("${python.script-path}")
    private String scriptPath;

    @Value("${python.python-path:python}")
    private String pythonPath;

    @Value("${file.data-dir:./data}")
    private String dataDir;

    private final QwenConfig qwenConfig;
    private final RedisTemplate<String, Object> redisTemplate;
    private final ObjectMapper objectMapper;

    // 活跃进程计数器
    private final AtomicInteger activeProcesses = new AtomicInteger(0);

    // 进程信号量，控制并发数
    // 支持一次处理8个PDF，至少同时处理3个
    private Semaphore processSemaphore;

    // 任务进度缓存前缀
    private static final String PROGRESS_KEY_PREFIX = "task:progress:";

    /**
     * 启动时清理残留的输入文件
     */
    @PostConstruct
    public void cleanupStaleInputFiles() {
        processSemaphore = new Semaphore(Math.max(1, qwenConfig.getMaxConcurrent()), true);
        log.info("Python处理并发槽初始化: {}", qwenConfig.getMaxConcurrent());

        try {
            Path workerDir = Paths.get(pythonWorkerDir);
            if (!Files.exists(workerDir)) return;

            File[] staleFiles = workerDir.toFile().listFiles((dir, name) ->
                    name.startsWith("input_") && name.endsWith(".json"));
            if (staleFiles != null) {
                for (File stale : staleFiles) {
                    // 只清理创建超过1小时的残留文件
                    if (System.currentTimeMillis() - stale.lastModified() > 3600000L) {
                        try {
                            Files.deleteIfExists(stale.toPath());
                            log.info("已清理残留输入文件: {}", stale.getName());
                        } catch (IOException e) {
                            log.warn("清理残留文件失败: {}", stale.getName());
                        }
                    }
                }
            }
        } catch (Exception e) {
            log.warn("清理残留输入文件时出错: {}", e.getMessage());
        }
    }

    /**
     * 处理提取任务
     */
    public Map<String, Object> processTask(Task task, String extractFieldsJson, String modelMode, String inferenceConfigJson) {
        String progressKey = PROGRESS_KEY_PREFIX + task.getTaskId();
        boolean semaphoreAcquired = false;
        boolean processRegistered = false;
        Path inputFilePath = null;

        try {
            // 获取信号量（限制并发）
            if (!processSemaphore.tryAcquire(qwenConfig.getTaskTimeout(), TimeUnit.SECONDS)) {
                throw new RuntimeException("获取处理槽位超时，请稍后重试");
            }

            semaphoreAcquired = true;
            activeProcesses.incrementAndGet();
            processRegistered = true;
            log.info("开始处理任务: taskId={}, modelMode={}, 活跃进程数={}", task.getTaskId(), modelMode, activeProcesses.get());

            // 更新进度：准备阶段
            updateProgress(progressKey, TaskProgressDTO.of(task.getTaskId(), "UPLOADING", 10));

            // 准备输入数据（包含 modelMode）
            Map<String, Object> inputData = prepareInputData(task, extractFieldsJson, modelMode, inferenceConfigJson);
            inputFilePath = writeInputFile(task, inputData);

            // 更新进度：OCR阶段
            updateProgress(progressKey, TaskProgressDTO.of(task.getTaskId(), "OCR_PROCESSING", 30));

            // 执行Python脚本（带重试）
            Map<String, Object> result = executeWithRetry(inputFilePath, progressKey, task.getTaskId());

            // 更新进度：完成
            updateProgress(progressKey, TaskProgressDTO.of(task.getTaskId(), "COMPLETED", 100));

            // 缓存结果
            cacheTaskResult(task.getTaskId(), result);

            return result;

        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("任务被中断");
        } catch (Exception e) {
            log.error("任务处理失败: taskId={}", task.getTaskId(), e);
            updateProgress(progressKey, TaskProgressDTO.builder()
                    .taskId(task.getTaskId())
                    .stage("FAILED")
                    .stageText("处理失败")
                    .errorMessage(e.getMessage())
                    .build());
            throw new RuntimeException("处理失败: " + e.getMessage());
        } finally {
            // 清理临时输入文件
            if (inputFilePath != null) {
                try {
                    Files.deleteIfExists(inputFilePath);
                } catch (IOException ex) {
                    log.warn("清理输入文件失败: {}", inputFilePath, ex);
                }
            }
            if (processRegistered) {
                activeProcesses.decrementAndGet();
            }
            if (semaphoreAcquired) {
                processSemaphore.release();
            }
        }
    }

    /**
     * 带重试机制的执行
     */
    private Map<String, Object> executeWithRetry(Path inputFilePath,
                                                  String progressKey, Long taskId) {
        Exception lastException = null;

        for (int attempt = 1; attempt <= qwenConfig.getMaxRetries(); attempt++) {
            try {
                log.info("执行Python脚本: taskId={}, 尝试 {}/{}", taskId, attempt, qwenConfig.getMaxRetries());

                // 更新进度：AI提取阶段
                int baseProgress = 50 + (attempt - 1) * 15;
                updateProgress(progressKey, TaskProgressDTO.of(taskId, "QWEN_EXTRACTING", baseProgress));

                Map<String, Object> result = executePythonScript(inputFilePath, progressKey, taskId);

                if ("success".equals(result.get("status"))) {
                    return result;
                }

                // 如果返回了部分数据，也算成功
                if (result.containsKey("data") && result.get("data") != null) {
                    result.put("partial", true);
                    return result;
                }

            } catch (Exception e) {
                lastException = e;
                log.warn("尝试 {}/{} 失败: {}", attempt, qwenConfig.getMaxRetries(), e.getMessage());

                if (attempt < qwenConfig.getMaxRetries()) {
                    try {
                        Thread.sleep(qwenConfig.getRetryInterval() * 1000L);
                    } catch (InterruptedException ie) {
                        Thread.currentThread().interrupt();
                        break;
                    }
                }
            }
        }

        throw new RuntimeException("重试" + qwenConfig.getMaxRetries() + "次后仍然失败: " +
                (lastException != null ? lastException.getMessage() : "未知错误"));
    }

    /**
     * 执行Python脚本
     */
    private Map<String, Object> executePythonScript(Path inputFilePath,
                                                     String progressKey, Long taskId) throws Exception {
        File scriptFile = new File(pythonWorkerDir, scriptPath);

        if (!scriptFile.exists()) {
            log.warn("Python脚本不存在，返回模拟数据: {}", scriptFile.getAbsolutePath());
            return generateMockResult();
        }

        List<String> command = buildCommand(inputFilePath);
        ProcessBuilder pb = new ProcessBuilder(command);
        pb.directory(new File(pythonWorkerDir));

        // 设置环境变量
        Map<String, String> env = pb.environment();
        env.put("PYTHONIOENCODING", "utf-8");
        env.put("PYTHONPATH", pythonWorkerDir + File.pathSeparator + env.getOrDefault("PYTHONPATH", ""));

        log.info("启动Python进程: {}", command);
        Process process = pb.start();

        CompletableFuture<String> stdoutFuture = CompletableFuture.supplyAsync(
                () -> readProcessStream(process.getInputStream(), false, progressKey, taskId));
        CompletableFuture<String> stderrFuture = CompletableFuture.supplyAsync(
                () -> readProcessStream(process.getErrorStream(), true, progressKey, taskId));

        boolean finished = process.waitFor(qwenConfig.getTaskTimeout(), TimeUnit.SECONDS);
        if (!finished) {
            process.destroyForcibly();
            process.waitFor(5, TimeUnit.SECONDS);
            throw new RuntimeException("处理超时 (" + qwenConfig.getTaskTimeout() + "秒)");
        }

        String stdoutText = stdoutFuture.get(5, TimeUnit.SECONDS).trim();
        String stderrText = stderrFuture.get(5, TimeUnit.SECONDS).trim();
        int exitCode = process.exitValue();

        if (exitCode != 0) {
            String failureDetail = extractPythonFailureDetail(stdoutText, stderrText);

            log.error("Python脚本执行失败: exitCode={}, stdout={}, stderr={}",
                    exitCode, stdoutText, stderrText);

            if (failureDetail.isBlank()) {
                // 无结构化错误信息，提取stderr尾部作为诊断信息
                failureDetail = stderrText.isBlank()
                        ? "子进程异常退出，无错误输出"
                        : stderrText.substring(Math.max(0, stderrText.length() - 500));
            }
            String workerHint = "（检查 MINERU_API_KEY 和 DASHSCOPE_API_KEY 环境变量是否正确配置）";
            throw new RuntimeException("PDF解析失败（退出码: " + exitCode + "）。"
                    + failureDetail + " " + workerHint);
        }

        return parseOutput(stdoutText);
    }


    private List<String> buildCommand(Path inputFilePath) {
        List<String> command = new ArrayList<>();
        command.add(pythonPath);
        command.add(scriptPath);
        command.add(inputFilePath.toString());
        return command;
    }

    private String readProcessStream(InputStream stream, boolean stderr, String progressKey, Long taskId) {
        StringBuilder output = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                output.append(line).append('\n');
                if (stderr) {
                    log.debug("Python日志: {}", line);
                    parseProgressUpdate(line, progressKey, taskId);
                }
            }
        } catch (IOException e) {
            log.debug("读取Python{}结束: {}", stderr ? "日志" : "输出", e.getMessage());
        }
        return output.toString();
    }

    /**
     * 解析进度更新
     */
    private void parseProgressUpdate(String line, String progressKey, Long taskId) {
        try {
            if (line.contains("\"progress\":")) {
                // 尝试解析JSON格式的进度信息
                if (line.startsWith("{") && line.endsWith("}")) {
                    Map<String, Object> progressInfo = objectMapper.readValue(line, Map.class);
                    int progress = (Integer) progressInfo.getOrDefault("progress", 0);
                    String stage = (String) progressInfo.getOrDefault("stage", "QWEN_EXTRACTING");
                    updateProgress(progressKey, TaskProgressDTO.of(taskId, stage, progress));
                }
            }
        } catch (Exception e) {
            // 忽略解析错误
        }
    }

    /**
     * 解析输出
     */
    private Map<String, Object> parseOutput(String outputStr) {
        if (outputStr.isEmpty()) {
            throw new RuntimeException("Python脚本无输出");
        }

        // 尝试提取JSON部分
        String jsonStr = extractJsonObject(outputStr);

        try {
            return objectMapper.readValue(jsonStr, Map.class);
        } catch (Exception e) {
            log.error("解析Python输出失败: {}", jsonStr, e);
            throw new RuntimeException("解析结果失败: " + e.getMessage());
        }
    }

    private String extractPythonFailureDetail(String stdoutText, String stderrText) {
        String stdoutMessage = parseErrorMessageFromJson(stdoutText);
        if (stdoutMessage != null && !stdoutMessage.isBlank()) {
            return stdoutMessage;
        }
        if (stdoutText != null && !stdoutText.isBlank()) {
            return stdoutText;
        }

        String stderrMessage = parseErrorMessageFromJson(stderrText);
        if (stderrMessage != null && !stderrMessage.isBlank()) {
            return stderrMessage;
        }
        if (stderrText != null && !stderrText.isBlank()) {
            return stderrText;
        }

        return "";
    }

    private String parseErrorMessageFromJson(String text) {
        if (text == null || text.isBlank()) {
            return null;
        }

        try {
            String jsonText = extractJsonObject(text);
            Map<String, Object> payload = objectMapper.readValue(jsonText, Map.class);
            Object message = payload.get("message");
            if (message != null) {
                return String.valueOf(message).trim();
            }
        } catch (Exception ignored) {
            // Ignore non-JSON output and fall back to raw text.
        }

        return null;
    }

    private String extractJsonObject(String text) {
        if (text == null || text.isBlank()) {
            return text;
        }

        int jsonStart = text.indexOf('{');
        int jsonEnd = text.lastIndexOf('}');
        if (jsonStart >= 0 && jsonEnd > jsonStart) {
            return text.substring(jsonStart, jsonEnd + 1);
        }
        return text;
    }

    /**
     * 准备输入数据
     */
    private Map<String, Object> prepareInputData(Task task, String extractFieldsJson, String modelMode, String inferenceConfigJson) {
        Map<String, Object> inputData = new HashMap<>();
        inputData.put("taskId", task.getTaskId());
        inputData.put("taskName", task.getTaskName());
        inputData.put("userId", task.getUser().getUserId());
        inputData.put("modelMode", modelMode);  // 添加模型模式
        inputData.put("inferenceConfig", parseInferenceConfig(inferenceConfigJson));
        if (extractFieldsJson != null && !extractFieldsJson.isBlank()) {
            inputData.put("extractFieldsJson", extractFieldsJson);
        }

        if (task.getFilePath() != null) {
            String fileName = (String) task.getFilePath().get("fileName");
            String filePath = (String) task.getFilePath().get("filePath");
            String taskDataDir = (String) task.getFilePath().get("taskDataDir");

            // 构建PDF文件完整路径
            String pdfFullPath;
            if (taskDataDir != null) {
                pdfFullPath = Paths.get(taskDataDir, "pdf", filePath).toString();
            } else {
                // 兼容旧数据 - 使用相对路径
                pdfFullPath = Paths.get("data", "uploads", filePath).toString();
            }

            inputData.put("fileInfo", Map.of(
                    "fileName", fileName,
                    "filePath", pdfFullPath,
                    "taskDataDir", taskDataDir != null ? taskDataDir : Paths.get(dataDir, sanitizeTaskName(task.getTaskName())).toString()
            ));
        }

        // 添加Qwen配置
        inputData.put("qwenConfig", Map.of(
                "model", qwenConfig.getModel(),
                "maxImages", qwenConfig.getMaxImages(),
                "maxContextLength", qwenConfig.getMaxContextLength()
        ));

        return inputData;
    }

    private Map<String, Object> parseInferenceConfig(String inferenceConfigJson) {
        Map<String, Object> defaults = buildDefaultInferenceConfig();
        if (inferenceConfigJson == null || inferenceConfigJson.isBlank()) {
            return defaults;
        }
        try {
            Map<String, Object> parsed = objectMapper.readValue(inferenceConfigJson, Map.class);
            if (parsed == null || parsed.isEmpty()) {
                return defaults;
            }
            defaults.putAll(parsed);
            return defaults;
        } catch (Exception e) {
            log.warn("解析 inferenceConfig 失败，将使用默认参数: {}", inferenceConfigJson, e);
            return defaults;
        }
    }

    private Map<String, Object> buildDefaultInferenceConfig() {
        Map<String, Object> defaults = new HashMap<>();
        defaults.put("temperature", 0);
        defaults.put("topP", 1);
        defaults.put("topK", 1);
        defaults.put("maxTokens", 4096);
        return defaults;
    }

    /**
     * 清理任务名称，移除不安全的字符
     */
    private String sanitizeTaskName(String taskName) {
        if (taskName == null) return "unnamed";
        return taskName.replaceAll("[^a-zA-Z0-9\\u4e00-\\u9fa5_-]", "_");
    }

    /**
     * 写入输入文件
     */
    private Path writeInputFile(Task task, Map<String, Object> inputData) throws Exception {
        String inputFileName = "input_" + task.getTaskId() + "_" + System.currentTimeMillis() + ".json";
        Path inputFilePath = Paths.get(pythonWorkerDir, inputFileName);
        objectMapper.writeValue(inputFilePath.toFile(), inputData);
        log.debug("输入数据已写入: {}", inputFilePath);
        return inputFilePath;
    }

    /**
     * 更新进度
     */
    private void updateProgress(String key, TaskProgressDTO progress) {
        try {
            redisTemplate.opsForValue().set(key, progress, Duration.ofHours(24));
            log.debug("进度更新: taskId={}, stage={}, progress={}%",
                    progress.getTaskId(), progress.getStage(), progress.getProgress());
        } catch (Exception e) {
            log.warn("更新进度失败: {}", e.getMessage());
        }
    }

    /**
     * 获取任务进度
     */
    public TaskProgressDTO getProgress(Long taskId) {
        String key = PROGRESS_KEY_PREFIX + taskId;
        return (TaskProgressDTO) redisTemplate.opsForValue().get(key);
    }

    /**
     * 缓存任务结果
     */
    private void cacheTaskResult(Long taskId, Map<String, Object> result) {
        String key = "task:result:" + taskId;
        redisTemplate.opsForValue().set(key, result, Duration.ofHours(24));
    }

    /**
     * 获取缓存的任务结果
     */
    public Map<String, Object> getCachedResult(Long taskId) {
        String key = "task:result:" + taskId;
        return (Map<String, Object>) redisTemplate.opsForValue().get(key);
    }

    /**
     * 获取当前活跃进程数
     */
    public int getActiveProcessCount() {
        return activeProcesses.get();
    }

    /**
     * 生成模拟结果
     */
    private Map<String, Object> generateMockResult() {
        Map<String, Object> mockResult = new HashMap<>();
        mockResult.put("status", "success");
        mockResult.put("message", "模拟处理完成");
        mockResult.put("model", qwenConfig.getModel());

        Map<String, Object> extractedData = new LinkedHashMap<>();
        extractedData.put("名称", "示例材料");
        extractedData.put("熔点", "85-87°C");
        extractedData.put("沸点", "210-212°C");
        extractedData.put("分子量", "256.34");
        extractedData.put("溶解度", "易溶于乙醇、丙酮");
        extractedData.put("密度", "1.23 g/cm³");

        mockResult.put("data", extractedData);
        mockResult.put("confidence", 0.95);
        return mockResult;
    }
}
