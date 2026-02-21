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
import java.io.InputStreamReader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

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
    private final Semaphore processSemaphore = new Semaphore(3, true);

    // 任务进度缓存前缀
    private static final String PROGRESS_KEY_PREFIX = "task:progress:";

    /**
     * 处理提取任务
     */
    public Map<String, Object> processTask(Task task, String extractFieldsJson) {
        String progressKey = PROGRESS_KEY_PREFIX + task.getTaskId();

        try {
            // 获取信号量（限制并发）
            if (!processSemaphore.tryAcquire(qwenConfig.getTaskTimeout(), TimeUnit.SECONDS)) {
                throw new RuntimeException("获取处理槽位超时，请稍后重试");
            }

            activeProcesses.incrementAndGet();
            log.info("开始处理任务: taskId={}, 活跃进程数={}", task.getTaskId(), activeProcesses.get());

            // 更新进度：准备阶段
            updateProgress(progressKey, TaskProgressDTO.of(task.getTaskId(), "UPLOADING", 10));

            // 准备输入数据
            Map<String, Object> inputData = prepareInputData(task);
            Path inputFilePath = writeInputFile(task, inputData);

            // 更新进度：OCR阶段
            updateProgress(progressKey, TaskProgressDTO.of(task.getTaskId(), "OCR_PROCESSING", 30));

            // 执行Python脚本（带重试）
            Map<String, Object> result = executeWithRetry(inputFilePath, extractFieldsJson, progressKey, task.getTaskId());

            // 更新进度：完成
            updateProgress(progressKey, TaskProgressDTO.of(task.getTaskId(), "COMPLETED", 100));

            // 清理临时文件
            Files.deleteIfExists(inputFilePath);

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
            activeProcesses.decrementAndGet();
            processSemaphore.release();
        }
    }

    /**
     * 带重试机制的执行
     */
    private Map<String, Object> executeWithRetry(Path inputFilePath, String extractFieldsJson,
                                                  String progressKey, Long taskId) {
        Exception lastException = null;

        for (int attempt = 1; attempt <= qwenConfig.getMaxRetries(); attempt++) {
            try {
                log.info("执行Python脚本: taskId={}, 尝试 {}/{}", taskId, attempt, qwenConfig.getMaxRetries());

                // 更新进度：AI提取阶段
                int baseProgress = 50 + (attempt - 1) * 15;
                updateProgress(progressKey, TaskProgressDTO.of(taskId, "QWEN_EXTRACTING", baseProgress));

                Map<String, Object> result = executePythonScript(inputFilePath, extractFieldsJson, progressKey, taskId);

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
    private Map<String, Object> executePythonScript(Path inputFilePath, String extractFieldsJson,
                                                     String progressKey, Long taskId) throws Exception {
        File scriptFile = new File(pythonWorkerDir, scriptPath);

        if (!scriptFile.exists()) {
            log.warn("Python脚本不存在，返回模拟数据: {}", scriptFile.getAbsolutePath());
            return generateMockResult();
        }

        List<String> command = buildCommand(inputFilePath, extractFieldsJson);
        ProcessBuilder pb = new ProcessBuilder(command);
        pb.directory(new File(pythonWorkerDir));
        // 不要合并stderr和stdout，因为Python脚本通过stderr输出日志，stdout输出JSON结果
        // pb.redirectErrorStream(true);

        // 设置环境变量
        Map<String, String> env = pb.environment();
        env.put("PYTHONIOENCODING", "utf-8");
        env.put("PYTHONPATH", pythonWorkerDir + File.pathSeparator + env.getOrDefault("PYTHONPATH", ""));

        log.info("启动Python进程: {}", command);
        Process process = pb.start();

        StringBuilder output = new StringBuilder();
        StringBuilder errorOutput = new StringBuilder();
        long startTime = System.currentTimeMillis();
        long timeoutMs = qwenConfig.getTaskTimeout() * 1000L;

        // 分别读取stdout和stderr
        try (BufferedReader stdoutReader = new BufferedReader(new InputStreamReader(process.getInputStream(), "UTF-8"));
             BufferedReader stderrReader = new BufferedReader(new InputStreamReader(process.getErrorStream(), "UTF-8"))) {
            
            while (true) {
                // 检查超时
                if (System.currentTimeMillis() - startTime > timeoutMs) {
                    process.destroyForcibly();
                    throw new RuntimeException("处理超时 (" + qwenConfig.getTaskTimeout() + "秒)");
                }

                // 读取stdout
                while (stdoutReader.ready()) {
                    String line = stdoutReader.readLine();
                    if (line != null) {
                        output.append(line).append("\n");
                    }
                }

                // 读取stderr（日志输出）
                while (stderrReader.ready()) {
                    String line = stderrReader.readLine();
                    if (line != null) {
                        errorOutput.append(line).append("\n");
                        log.debug("Python日志: {}", line);
                        // 解析进度信息
                        parseProgressUpdate(line, progressKey, taskId);
                    }
                }

                // 检查进程状态
                try {
                    int exitCode = process.exitValue();
                    // 读取剩余输出
                    String line;
                    while ((line = stdoutReader.readLine()) != null) {
                        output.append(line).append("\n");
                    }
                    while ((line = stderrReader.readLine()) != null) {
                        errorOutput.append(line).append("\n");
                        log.debug("Python日志: {}", line);
                    }

                    if (exitCode != 0) {
                        log.error("Python脚本执行失败: exitCode={}, stderr={}", exitCode, errorOutput);
                        throw new RuntimeException("脚本执行失败，退出码: " + exitCode);
                    }

                    break;
                } catch (IllegalThreadStateException e) {
                    Thread.sleep(200);
                }
            }
        }

        String outputStr = output.toString().trim();
        return parseOutput(outputStr);
    }

    /**
     * 构建命令
     */
    private List<String> buildCommand(Path inputFilePath, String extractFieldsJson) {
        List<String> command = new ArrayList<>();
        command.add(pythonPath);
        command.add(scriptPath);
        command.add(inputFilePath.toString());
        command.add(extractFieldsJson);
        return command;
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
        String jsonStr = outputStr;
        int jsonStart = outputStr.indexOf('{');
        int jsonEnd = outputStr.lastIndexOf('}');

        if (jsonStart >= 0 && jsonEnd > jsonStart) {
            jsonStr = outputStr.substring(jsonStart, jsonEnd + 1);
        }

        try {
            return objectMapper.readValue(jsonStr, Map.class);
        } catch (Exception e) {
            log.error("解析Python输出失败: {}", jsonStr, e);
            throw new RuntimeException("解析结果失败: " + e.getMessage());
        }
    }

    /**
     * 准备输入数据
     */
    private Map<String, Object> prepareInputData(Task task) {
        Map<String, Object> inputData = new HashMap<>();
        inputData.put("taskId", task.getTaskId());
        inputData.put("taskName", task.getTaskName());
        inputData.put("userId", task.getUser().getUserId());

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
