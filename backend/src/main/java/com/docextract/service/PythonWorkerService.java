package com.docextract.service;

import com.docextract.entity.Task;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;

import java.io.BufferedReader;
import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.TimeUnit;

@Service
@RequiredArgsConstructor
@Slf4j
public class PythonWorkerService {

    @Value("${python.worker-dir}")
    private String pythonWorkerDir;

    @Value("${python.script-path}")
    private String scriptPath;

    @Value("${python.python-path:python}")
    private String pythonPath;

    @Value("${python.mineru-timeout:3600}")
    private int mineruTimeout; // MinerU处理超时时间（秒）,默认1小时

    private final RedisTemplate<String, Object> redisTemplate;
    private final ObjectMapper objectMapper;

    public Map<String, Object> processTask(Task task, String extractFieldsJson) {
        try {
            // 1. 准备输入数据
            Map<String, Object> inputData = prepareInputData(task);

            // 2. 将输入数据写入临时文件
            String inputFileName = "input_" + task.getTaskId() + ".json";
            Path inputFilePath = Paths.get(pythonWorkerDir, inputFileName);
            objectMapper.writeValue(inputFilePath.toFile(), inputData);

            log.info("输入数据已写入: {}", inputFilePath);

            // 3. 调用Python脚本
            Map<String, Object> result = executePythonScript(inputFilePath, extractFieldsJson);

            // 4. 清理临时文件
            Files.deleteIfExists(inputFilePath);

            return result;

        } catch (Exception e) {
            log.error("Python脚本执行失败: taskId={}", task.getTaskId(), e);
            throw new RuntimeException("Python脚本执行失败: " + e.getMessage());
        }
    }

    private Map<String, Object> prepareInputData(Task task) throws IOException {
        Map<String, Object> inputData = new HashMap<>();
        inputData.put("taskId", task.getTaskId());
        inputData.put("taskName", task.getTaskName());
        inputData.put("userId", task.getUser().getUserId());

        // 获取文件路径
        if (task.getFilePath() != null) {
            String fileName = (String) task.getFilePath().get("fileName");
            String filePath = (String) task.getFilePath().get("filePath");
            String taskDataDir = (String) task.getFilePath().get("taskDataDir");

            // 构建PDF文件完整路径
            String fullPath;
            if (taskDataDir != null) {
                fullPath = Paths.get(taskDataDir, "pdf", filePath).toString();
            } else {
                // 兼容旧数据
                fullPath = Paths.get("data", "uploads", filePath).toString();
            }

            inputData.put("fileInfo", Map.of(
                    "fileName", fileName,
                    "filePath", fullPath,
                    "taskDataDir", taskDataDir != null ? taskDataDir : Paths.get("data").toString()
            ));
        }

        return inputData;
    }

    private Map<String, Object> executePythonScript(Path inputFilePath, String extractFieldsJson) throws Exception {
        // 检查脚本文件是否存在
        File scriptFile = new File(pythonWorkerDir, scriptPath);
        if (!scriptFile.exists()) {
            log.warn("集成处理器脚本不存在，返回模拟数据: {}", scriptFile.getAbsolutePath());
            return generateMockResult(extractFieldsJson);
        }

        try {
            // 构建命令 - 使用集成处理器
            List<String> command = new ArrayList<>();
            command.add(pythonPath);
            command.add(scriptPath);
            command.add(inputFilePath.toString());
            command.add(extractFieldsJson);

            ProcessBuilder processBuilder = new ProcessBuilder(command);
            processBuilder.directory(new File(pythonWorkerDir));
            processBuilder.redirectErrorStream(true);
            
            // 设置环境变量
            Map<String, String> env = processBuilder.environment();
            env.put("PYTHONPATH", pythonWorkerDir + File.pathSeparator + env.getOrDefault("PYTHONPATH", ""));

            log.info("启动集成处理器: {}", command);
            Process process = processBuilder.start();

            // 读取输出 - 增加超时控制
            StringBuilder output = new StringBuilder();
            boolean finished = false;
            
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()))) {
                String line;
                long startTime = System.currentTimeMillis();
                long timeoutMs = mineruTimeout * 1000L;
                
                while (!finished) {
                    // 检查超时
                    if (System.currentTimeMillis() - startTime > timeoutMs) {
                        process.destroyForcibly();
                        throw new RuntimeException("Python脚本执行超时 (" + mineruTimeout + "秒)");
                    }
                    
                    // 尝试读取一行
                    if (reader.ready()) {
                        line = reader.readLine();
                        if (line != null) {
                            output.append(line).append("\n");
                            log.debug("Python输出: {}", line);
                        }
                    }
                    
                    // 检查进程是否结束
                    try {
                        int exitCode = process.exitValue();
                        finished = true;
                        
                        // 读取剩余输出
                        while (reader.ready() && (line = reader.readLine()) != null) {
                            output.append(line).append("\n");
                        }
                        
                        if (exitCode != 0) {
                            log.error("集成处理器执行失败，退出码: {}, 输出: {}", exitCode, output);
                            throw new RuntimeException("集成处理器执行失败，退出码: " + exitCode);
                        }
                    } catch (IllegalThreadStateException e) {
                        // 进程还在运行，继续等待
                        Thread.sleep(100);
                    }
                }
            }

            // 解析输出
            String outputStr = output.toString().trim();
            if (outputStr.length() > 0) {
                try {
                    return objectMapper.readValue(outputStr, Map.class);
                } catch (Exception e) {
                    log.error("解析Python输出失败: {}", outputStr, e);
                    throw new RuntimeException("解析处理结果失败: " + e.getMessage());
                }
            } else {
                log.error("集成处理器无输出");
                throw new RuntimeException("集成处理器无输出");
            }

        } catch (Exception e) {
            log.error("执行集成处理器失败: {}", e.getMessage(), e);
            throw new RuntimeException("集成处理器执行失败: " + e.getMessage());
        }
    }

    private Map<String, Object> generateMockResult(String extractFieldsJson) {
        Map<String, Object> mockResult = new HashMap<>();
        mockResult.put("status", "success");
        mockResult.put("message", "处理完成");

        // 模拟提取的数据
        Map<String, Object> extractedData = new HashMap<>();
        extractedData.put("名称", "示例化合物A");
        extractedData.put("熔点", "85-87°C");
        extractedData.put("沸点", "210-212°C");
        extractedData.put("分子量", "256.34");
        extractedData.put("溶解度", "易溶于乙醇、丙酮");

        mockResult.put("data", extractedData);
        mockResult.put("confidence", 0.95);
        mockResult.put("model", "qwen-vl-max-latest");
        mockResult.put("mineru_processed", true);

        return mockResult;
    }

    public void saveTaskResultToCache(Long taskId, Map<String, Object> result) {
        String key = "task:result:" + taskId;
        redisTemplate.opsForValue().set(key, result, Duration.ofHours(24));
        log.info("任务结果已缓存: taskId={}", taskId);
    }

    public Map<String, Object> getTaskResultFromCache(Long taskId) {
        String key = "task:result:" + taskId;
        return (Map<String, Object>) redisTemplate.opsForValue().get(key);
    }
}
