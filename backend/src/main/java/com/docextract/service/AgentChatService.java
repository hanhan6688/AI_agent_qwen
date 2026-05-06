package com.docextract.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.PreDestroy;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.File;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Duration;
import java.util.Comparator;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Semaphore;

@Service
@Slf4j
public class AgentChatService {

    private static final ObjectMapper OBJECT_MAPPER = new ObjectMapper();
    private static final long CHAT_TIMEOUT_SECONDS = 240;
    private static final long STREAM_TIMEOUT_SECONDS = 600;

    @Value("${python.worker-dir}")
    private String pythonWorkerDir;

    @Value("${python.python-path}")
    private String pythonPath;

    private final ExecutorService streamExecutor = Executors.newFixedThreadPool(4);
    private final Semaphore streamSemaphore = new Semaphore(4, true);

    @PreDestroy
    public void shutdownStreamExecutor() {
        streamExecutor.shutdownNow();
    }

    public Map<String, Object> chat(String message, Object history, String mode) {
        Path inputFile = null;
        try {
            Map<String, Object> payload = new LinkedHashMap<>();
            payload.put("message", message);
            payload.put("history", history);
            payload.put("mode", normalizeMode(mode));

            Path workerDir = Paths.get(pythonWorkerDir);
            Files.createDirectories(workerDir);
            inputFile = Files.createTempFile(workerDir, "agent_chat_", ".json");
            Files.writeString(inputFile, OBJECT_MAPPER.writeValueAsString(payload), StandardCharsets.UTF_8);

            List<String> command = new ArrayList<>();
            command.add(pythonPath);
            command.add("agent_chat.py");
            command.add(inputFile.toString());

            ProcessBuilder processBuilder = new ProcessBuilder(command);
            processBuilder.directory(new File(pythonWorkerDir));
            processBuilder.environment().put("PYTHONIOENCODING", "utf-8");
            processBuilder.environment().put(
                    "PYTHONPATH",
                    pythonWorkerDir + File.pathSeparator + processBuilder.environment().getOrDefault("PYTHONPATH", "")
            );

            Process process = processBuilder.start();
            boolean finished = process.waitFor(CHAT_TIMEOUT_SECONDS, TimeUnit.SECONDS);
            if (!finished) {
                process.destroyForcibly();
                throw new RuntimeException("智能体对话超时 (" + Duration.ofSeconds(CHAT_TIMEOUT_SECONDS).toSeconds() + "秒)");
            }

            String stdout = new String(process.getInputStream().readAllBytes(), StandardCharsets.UTF_8).trim();
            String stderr = new String(process.getErrorStream().readAllBytes(), StandardCharsets.UTF_8).trim();
            if (!stderr.isBlank()) {
                log.debug("智能体对话脚本日志: {}", stderr);
            }

            if (process.exitValue() != 0) {
                throw new RuntimeException(extractPythonError(stdout, stderr));
            }

            Map<String, Object> result = OBJECT_MAPPER.readValue(extractJsonObject(stdout), Map.class);
            if (!"success".equals(result.get("status"))) {
                throw new RuntimeException(String.valueOf(result.getOrDefault("message", "智能体对话失败")));
            }
            result.remove("status");
            return result;
        } catch (Exception e) {
            log.error("智能体对话失败", e);
            throw new RuntimeException(e.getMessage(), e);
        } finally {
            if (inputFile != null) {
                try {
                    Files.deleteIfExists(inputFile);
                } catch (Exception ignored) {
                    // ignore temporary file cleanup failures
                }
            }
        }
    }

    public Map<String, Object> profile() {
        Map<String, Object> profile = new LinkedHashMap<>();
        profile.put("title", "基于通义千问大模型的智能指标提取智能体");
        profile.put("agentName", "智能指标提取智能体");
        profile.put("normalMode", "普通版：保留智能路由；无图片输入走 qwen-long，有图片输入时走 qwen3.6-plus，不做 qwen3-vl-plus 前置筛图。");
        profile.put("proMode", "专业版：qwen3-vl-plus 先筛图、理解图片和结构化表格，再交给 qwen3.6-plus 统一抽取。");
        profile.put("chatModel", "LangChain + qwen3.6-plus 流式对话，支持 Markdown/JSON 渲染和 PDF 附件上下文。");
        profile.put("router", "对话先经过 LangChain Router，判断普通问答、字段配置、文档解析、结果解释或导出任务，并给出推荐链路。");
        profile.put("output", "结果只保留用户配置字段，并尽量展开多组对照，方便导出 CSV/Excel。");
        return profile;
    }

    public void streamChat(String message, String historyJson, String mode, MultipartFile[] files, SseEmitter emitter) {
        CompletableFuture.runAsync(() -> {
            Path inputFile = null;
            Path uploadDir = null;
            Process process = null;
            boolean permitAcquired = false;
            try {
                if (!streamSemaphore.tryAcquire(5, TimeUnit.SECONDS)) {
                    sendSse(emitter, "error", Map.of("message", "当前智能体对话较忙，请稍后重试"));
                    emitter.complete();
                    return;
                }
                permitAcquired = true;

                Path workerDir = Paths.get(pythonWorkerDir);
                Files.createDirectories(workerDir);
                uploadDir = Files.createTempDirectory(workerDir, "agent_chat_upload_");

                Map<String, Object> payload = new LinkedHashMap<>();
                payload.put("message", message);
                payload.put("history", parseHistory(historyJson));
                payload.put("mode", normalizeMode(mode));
                payload.put("files", saveChatFiles(files, uploadDir));

                inputFile = Files.createTempFile(workerDir, "agent_langchain_", ".json");
                Files.writeString(inputFile, OBJECT_MAPPER.writeValueAsString(payload), StandardCharsets.UTF_8);

                List<String> command = new ArrayList<>();
                command.add(pythonPath);
                command.add("agent_langchain_stream.py");
                command.add(inputFile.toString());

                ProcessBuilder processBuilder = new ProcessBuilder(command);
                processBuilder.directory(new File(pythonWorkerDir));
                processBuilder.environment().put("PYTHONIOENCODING", "utf-8");
                processBuilder.environment().put(
                        "PYTHONPATH",
                        pythonWorkerDir + File.pathSeparator + processBuilder.environment().getOrDefault("PYTHONPATH", "")
                );

                log.info("启动LangChain流式智能体: {}", command);
                process = processBuilder.start();
                Process runningProcess = process;

                CompletableFuture<Void> stderrReader = CompletableFuture.runAsync(() -> readProcessLog(runningProcess));
                readAndForwardStream(runningProcess, emitter);

                boolean finished = runningProcess.waitFor(STREAM_TIMEOUT_SECONDS, TimeUnit.SECONDS);
                if (!finished) {
                    runningProcess.destroyForcibly();
                    sendSse(emitter, "error", Map.of("message", "LangChain流式对话超时"));
                } else if (runningProcess.exitValue() != 0) {
                    log.warn("LangChain流式智能体异常退出: exitCode={}", runningProcess.exitValue());
                }
                stderrReader.get(5, TimeUnit.SECONDS);
                emitter.complete();
            } catch (Exception e) {
                log.error("LangChain流式对话失败", e);
                sendSse(emitter, "error", Map.of("message", e.getMessage() == null ? "流式对话失败" : e.getMessage()));
                emitter.completeWithError(e);
            } finally {
                if (process != null && process.isAlive()) {
                    process.destroyForcibly();
                }
                deleteQuietly(inputFile);
                deleteDirectoryQuietly(uploadDir);
                if (permitAcquired) {
                    streamSemaphore.release();
                }
            }
        }, streamExecutor);
    }

    private String normalizeMode(String mode) {
        if ("pro".equalsIgnoreCase(mode)) {
            return "pro";
        }
        return "normal";
    }

    private Object parseHistory(String historyJson) {
        if (historyJson == null || historyJson.isBlank()) {
            return List.of();
        }
        try {
            return OBJECT_MAPPER.readValue(historyJson, Object.class);
        } catch (Exception e) {
            log.warn("解析流式对话history失败，将忽略: {}", historyJson, e);
            return List.of();
        }
    }

    private List<Map<String, Object>> saveChatFiles(MultipartFile[] files, Path uploadDir) throws Exception {
        List<Map<String, Object>> savedFiles = new ArrayList<>();
        if (files == null || files.length == 0) {
            return savedFiles;
        }

        for (MultipartFile file : files) {
            if (file == null || file.isEmpty()) {
                continue;
            }

            String originalName = file.getOriginalFilename() == null ? "attachment.pdf" : file.getOriginalFilename();
            String ext = originalName.contains(".")
                    ? originalName.substring(originalName.lastIndexOf(".")).toLowerCase()
                    : ".pdf";
            if (!".pdf".equals(ext)) {
                throw new RuntimeException("对话框暂只支持上传 PDF 文件: " + originalName);
            }

            Path savedPath = uploadDir.resolve(System.currentTimeMillis() + "_" + sanitizeFileName(originalName));
            file.transferTo(savedPath.toFile());
            Map<String, Object> fileInfo = new LinkedHashMap<>();
            fileInfo.put("name", originalName);
            fileInfo.put("path", savedPath.toString());
            fileInfo.put("type", file.getContentType());
            fileInfo.put("size", file.getSize());
            savedFiles.add(fileInfo);
        }
        return savedFiles;
    }

    private String sanitizeFileName(String fileName) {
        return fileName.replaceAll("[\\\\/:*?\"<>|]", "_");
    }

    private void readAndForwardStream(Process process, SseEmitter emitter) throws Exception {
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                if (line.isBlank()) {
                    continue;
                }
                try {
                    Map<String, Object> packet = OBJECT_MAPPER.readValue(line, Map.class);
                    String event = String.valueOf(packet.getOrDefault("event", "message"));
                    Object data = packet.getOrDefault("data", Map.of());
                    sendSse(emitter, event, data);
                } catch (Exception parseEx) {
                    log.warn("解析LangChain流式输出失败: {}", line, parseEx);
                    sendSse(emitter, "delta", Map.of("content", line));
                }
            }
        }
    }

    private void readProcessLog(Process process) {
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(process.getErrorStream(), StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                if (!line.isBlank()) {
                    log.debug("LangChain智能体日志: {}", line);
                }
            }
        } catch (Exception e) {
            log.debug("读取LangChain日志结束: {}", e.getMessage());
        }
    }

    private void sendSse(SseEmitter emitter, String event, Object data) {
        try {
            emitter.send(SseEmitter.event().name(event).data(data));
        } catch (Exception e) {
            log.debug("发送SSE事件失败: {}", e.getMessage());
        }
    }

    private void deleteQuietly(Path path) {
        if (path == null) {
            return;
        }
        try {
            Files.deleteIfExists(path);
        } catch (Exception ignored) {
            // ignore cleanup failures
        }
    }

    private void deleteDirectoryQuietly(Path dir) {
        if (dir == null || !Files.exists(dir)) {
            return;
        }
        try {
            Files.walk(dir)
                    .sorted(Comparator.reverseOrder())
                    .forEach(this::deleteQuietly);
        } catch (Exception ignored) {
            // ignore cleanup failures
        }
    }

    private String extractPythonError(String stdout, String stderr) {
        try {
            if (stdout != null && !stdout.isBlank()) {
                Map<String, Object> payload = OBJECT_MAPPER.readValue(extractJsonObject(stdout), Map.class);
                Object message = payload.get("message");
                if (message != null) {
                    return String.valueOf(message);
                }
            }
        } catch (Exception ignored) {
            // fall back to raw output
        }
        if (stderr != null && !stderr.isBlank()) {
            return stderr;
        }
        return stdout == null || stdout.isBlank() ? "智能体对话脚本执行失败" : stdout;
    }

    private String extractJsonObject(String text) {
        if (text == null || text.isBlank()) {
            return "{}";
        }
        int start = text.indexOf('{');
        int end = text.lastIndexOf('}');
        if (start >= 0 && end > start) {
            return text.substring(start, end + 1);
        }
        return text;
    }
}
