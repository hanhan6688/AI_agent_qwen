package com.docextract.controller;

import com.docextract.dto.ApiResponse;
import com.docextract.dto.TaskCreateRequest;
import com.docextract.dto.TaskExcelUpdateRequest;
import com.docextract.dto.TaskErrorUpdateRequest;
import com.docextract.dto.TaskResponse;
import com.docextract.dto.TaskStatusUpdateRequest;
import com.docextract.entity.Task;
import com.docextract.service.TaskService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

@Slf4j
@RestController
@RequestMapping("/api/tasks")
@RequiredArgsConstructor
@CrossOrigin(origins = "*")
public class TaskController {

    private final TaskService taskService;

    @PostMapping
    public ApiResponse<List<TaskResponse>> createTask(
            @RequestParam("taskName") String taskName,
            @RequestParam("userId") Long userId,
            @RequestParam("extractFields") String extractFields,
            @RequestParam("files") List<MultipartFile> files
    ) {
        try {
            TaskCreateRequest request = new TaskCreateRequest(taskName, userId, extractFields);
            List<TaskResponse> responses = taskService.createBatchTasks(request, files);
            return ApiResponse.success("批量任务创建成功，共创建 " + responses.size() + " 个任务", responses);
        } catch (Exception e) {
            log.error("创建任务失败", e);
            return ApiResponse.error("创建任务失败: " + e.getMessage());
        }
    }

    @GetMapping("/{taskId}")
    public ApiResponse<TaskResponse> getTask(@PathVariable String taskId) {
        try {
            var task = taskService.getTaskById(taskId);
            return task.map(value -> ApiResponse.success(TaskResponse.fromEntity(value)))
                    .orElseGet(() -> ApiResponse.error(404, "任务不存在"));
        } catch (Exception e) {
            log.error("获取任务失败", e);
            return ApiResponse.error("获取任务失败: " + e.getMessage());
        }
    }

    @GetMapping
    public ApiResponse<Page<TaskResponse>> getUserTasks(
            @RequestParam Long userId,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "10") int size
    ) {
        try {
            Page<TaskResponse> tasks = taskService.getUserTasks(userId, page, size);
            return ApiResponse.success(tasks);
        } catch (Exception e) {
            log.error("获取任务列表失败", e);
            return ApiResponse.error("获取任务列表失败: " + e.getMessage());
        }
    }

    @DeleteMapping("/{taskId}")
    public ApiResponse<Void> deleteTask(@PathVariable String taskId) {
        try {
            taskService.deleteTask(taskId);
            return ApiResponse.success("任务删除成功", null);
        } catch (Exception e) {
            log.error("删除任务失败", e);
            return ApiResponse.error("删除任务失败: " + e.getMessage());
        }
    }

    @GetMapping("/{taskId}/status")
    public ApiResponse<TaskResponse> getTaskStatus(@PathVariable String taskId) {
        try {
            var task = taskService.getTaskById(taskId);
            return task.map(value -> ApiResponse.success(TaskResponse.fromEntity(value)))
                    .orElseGet(() -> ApiResponse.error(404, "任务不存在"));
        } catch (Exception e) {
            log.error("获取任务状态失败", e);
            return ApiResponse.error("获取任务状态失败: " + e.getMessage());
        }
    }

    /**
     * Worker API: 更新任务状态 (供Python Worker调用)
     */
    @PutMapping("/{taskId}/status")
    public ApiResponse<TaskResponse> updateTaskStatus(
            @PathVariable String taskId,
            @RequestBody TaskStatusUpdateRequest request
    ) {
        try {
            Task.TaskStatus status = Task.TaskStatus.valueOf(request.getStatus());
            TaskResponse response = taskService.updateTaskStatus(taskId, status);
            return ApiResponse.success("任务状态更新成功", response);
        } catch (Exception e) {
            log.error("更新任务状态失败", e);
            return ApiResponse.error("更新任务状态失败: " + e.getMessage());
        }
    }

    /**
     * Worker API: 更新任务Excel路径 (供Python Worker调用)
     */
    @PutMapping("/{taskId}/excel")
    public ApiResponse<TaskResponse> updateTaskExcel(
            @PathVariable String taskId,
            @RequestBody TaskExcelUpdateRequest request
    ) {
        try {
            TaskResponse response = taskService.updateTaskExcelPath(taskId, request.getExcelPath());
            return ApiResponse.success("任务Excel路径更新成功", response);
        } catch (Exception e) {
            log.error("更新任务Excel路径失败", e);
            return ApiResponse.error("更新任务Excel路径失败: " + e.getMessage());
        }
    }

    /**
     * Worker API: 更新任务错误信息 (供Python Worker调用)
     */
    @PutMapping("/{taskId}/error")
    public ApiResponse<TaskResponse> updateTaskError(
            @PathVariable String taskId,
            @RequestBody TaskErrorUpdateRequest request
    ) {
        try {
            TaskResponse response = taskService.updateTaskError(taskId, request.getErrorMessage());
            return ApiResponse.success("任务错误信息更新成功", response);
        } catch (Exception e) {
            log.error("更新任务错误信息失败", e);
            return ApiResponse.error("更新任务错误信息失败: " + e.getMessage());
        }
    }
}
