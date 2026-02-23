package com.docextract.controller;

import com.docextract.dto.Response;
import com.docextract.dto.TaskDTO;
import com.docextract.dto.TaskProgressDTO;
import com.docextract.service.TaskService;
import jakarta.validation.constraints.NotNull;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.util.List;
import java.util.Map;
import java.util.concurrent.*;

@RestController
@RequestMapping("/api/tasks")
@RequiredArgsConstructor
@Slf4j
public class TaskController {

    private final TaskService taskService;

    // SSE连接管理
    private final ConcurrentHashMap<Long, SseEmitter> emitters = new ConcurrentHashMap<>();
    private final ScheduledExecutorService scheduler = Executors.newScheduledThreadPool(2);

    /**
     * 创建提取任务
     */
    @PostMapping
    public Response<List<TaskDTO>> createTask(
            @RequestParam String taskName,
            @RequestParam String extractFields,
            @RequestParam Long userId,
            @RequestParam(value = "modelMode", defaultValue = "normal") String modelMode,
            @RequestParam("files") MultipartFile[] files) {

        log.info("创建任务: taskName={}, userId={}, modelMode={}, 文件数量={}", taskName, userId, modelMode, files.length);

        // 检查活跃任务数
        long activeCount = taskService.getActiveTaskCount(userId);
        if (activeCount >= 10) {
            return Response.error("您有太多正在处理的任务，请稍后再试");
        }

        List<TaskDTO> tasks = taskService.createTasks(userId, taskName, extractFields, modelMode, files);
        return Response.success("任务创建成功，正在后台处理", tasks);
    }

    /**
     * 分页获取用户任务
     */
    @GetMapping
    public Response<Page<TaskDTO>> getTasks(
            @RequestParam @NotNull Long userId,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "10") int size) {

        Page<TaskDTO> tasks = taskService.getTasksByUserId(userId, page, size);
        return Response.success(tasks);
    }

    /**
     * 获取任务详情
     */
    @GetMapping("/{taskId}")
    public Response<TaskDTO> getTask(@PathVariable Long taskId) {
        TaskDTO task = taskService.getTaskById(taskId);
        return Response.success(task);
    }

    /**
     * 获取任务状态
     */
    @GetMapping("/{taskId}/status")
    public Response<Map<String, Object>> getTaskStatus(@PathVariable Long taskId) {
        TaskDTO task = taskService.getTaskById(taskId);
        return Response.success(Map.of(
                "status", task.getStatus(),
                "statusText", task.getStatusText(),
                "progress", taskService.getTaskProgress(taskId)
        ));
    }

    /**
     * 获取任务进度
     */
    @GetMapping("/{taskId}/progress")
    public Response<TaskProgressDTO> getProgress(@PathVariable Long taskId) {
        TaskProgressDTO progress = taskService.getTaskProgress(taskId);
        return Response.success(progress);
    }

    /**
     * SSE实时进度推送
     */
    @GetMapping(value = "/{taskId}/progress/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter streamProgress(@PathVariable Long taskId) {
        SseEmitter emitter = new SseEmitter(300000L); // 5分钟超时

        // 存储emitter
        SseEmitter oldEmitter = emitters.put(taskId, emitter);
        if (oldEmitter != null) {
            oldEmitter.complete();
        }

        emitter.onCompletion(() -> emitters.remove(taskId));
        emitter.onTimeout(() -> emitters.remove(taskId));
        emitter.onError(e -> emitters.remove(taskId));

        // 定时推送进度
        ScheduledFuture<?> future = scheduler.scheduleAtFixedRate(() -> {
            try {
                TaskProgressDTO progress = taskService.getTaskProgress(taskId);
                if (progress != null) {
                    emitter.send(SseEmitter.event()
                            .name("progress")
                            .data(progress));

                    // 完成或失败时结束
                    if ("COMPLETED".equals(progress.getStage()) || "FAILED".equals(progress.getStage())) {
                        emitter.complete();
                    }
                }
            } catch (IOException e) {
                emitter.completeWithError(e);
            }
        }, 0, 2, TimeUnit.SECONDS);

        // 完成时取消定时任务
        emitter.onCompletion(() -> future.cancel(true));
        emitter.onTimeout(() -> future.cancel(true));

        return emitter;
    }

    /**
     * 重试失败任务
     */
    @PostMapping("/{taskId}/retry")
    public Response<TaskDTO> retryTask(
            @PathVariable Long taskId,
            @RequestParam String extractFields) {

        log.info("重试任务: taskId={}", taskId);
        TaskDTO task = taskService.retryTask(taskId, extractFields);
        return Response.success("任务已重新提交处理", task);
    }

    /**
     * 删除任务
     */
    @DeleteMapping("/{taskId}")
    public Response<Void> deleteTask(@PathVariable Long taskId) {
        taskService.deleteTask(taskId);
        return Response.success("任务删除成功", null);
    }

    /**
     * 批量删除任务
     */
    @DeleteMapping("/batch")
    public Response<Void> deleteTasks(@RequestBody List<Long> taskIds) {
        taskIds.forEach(taskService::deleteTask);
        return Response.success("批量删除成功", null);
    }

    /**
     * 打包json_data目录为zip保存到result目录，返回下载链接
     */
    @PostMapping("/create-json-zip")
    public Response<Map<String, Object>> createJsonZip(@RequestParam String taskName) {
        log.info("创建JSON zip: taskName={}", taskName);
        try {
            String zipPath = taskService.createJsonZip(taskName);
            String safeTaskName = taskName.replaceAll("[^a-zA-Z0-9\\u4e00-\\u9fa5_-]", "_");

            return Response.success("打包成功", Map.of(
                "zipPath", zipPath,
                "downloadUrl", "/api/files/download/result/" + safeTaskName + "/result/" + safeTaskName + ".zip",
                "fileName", safeTaskName + ".zip"
            ));
        } catch (Exception e) {
            log.error("打包失败: {}", e.getMessage());
            return Response.error("打包失败: " + e.getMessage());
        }
    }

    /**
     * 获取任务数据目录信息
     */
    @GetMapping("/data-dir/{taskName}")
    public Response<Map<String, Object>> getTaskDataDir(@PathVariable String taskName) {
        String dataDir = taskService.getTaskDataDir(taskName);
        String resultDir = taskService.getTaskResultDir(taskName);
        String zipPath = taskService.getJsonZipPath(taskName);
        
        java.io.File zipFile = new java.io.File(zipPath);
        
        return Response.success(Map.of(
            "dataDir", dataDir,
            "resultDir", resultDir,
            "zipExists", zipFile.exists(),
            "downloadUrl", zipFile.exists() ? 
                "/api/files/download/result/" + taskName + "/result/" + taskName.replaceAll("[^a-zA-Z0-9\\u4e00-\\u9fa5_-]", "_") + ".zip" 
                : null
        ));
    }

    /**
     * 获取用户的批量任务列表（按taskName分组）
     */
    @GetMapping("/batch")
    public Response<List<Map<String, Object>>> getBatchTasks(@RequestParam @NotNull Long userId) {
        List<Map<String, Object>> batchTasks = taskService.getBatchTasks(userId);
        return Response.success(batchTasks);
    }

    /**
     * 获取批量任务详情（该taskName下的所有子任务）
     */
    @GetMapping("/batch/{taskName}")
    public Response<List<TaskDTO>> getBatchTaskDetails(
            @RequestParam @NotNull Long userId,
            @PathVariable String taskName) {
        List<TaskDTO> tasks = taskService.getTasksByTaskName(userId, taskName);
        return Response.success(tasks);
    }

    /**
     * 删除批量任务
     */
    @DeleteMapping("/batch/{taskName}")
    public Response<Void> deleteBatchTask(
            @RequestParam @NotNull Long userId,
            @PathVariable String taskName) {
        taskService.deleteBatchTask(userId, taskName);
        return Response.success("批量任务删除成功", null);
    }
}
