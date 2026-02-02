package com.docextract.dto;

import com.docextract.entity.Task;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class TaskResponse {

    private String taskId;
    private String batchId;
    private Long userId;
    private String taskName;
    private String status;
    private String fileName;
    private Long fileSize;
    private Integer pdfCount;
    private String extractFields;
    private Integer priority;
    private LocalDateTime createdAt;
    private LocalDateTime startedAt;
    private LocalDateTime completedAt;
    private String errorMessage;
    private String excelPath;

    public static TaskResponse fromEntity(Task task) {
        return TaskResponse.builder()
                .taskId(task.getTaskId())
                .batchId(task.getBatchId())
                .userId(task.getUserId())
                .taskName(task.getTaskName())
                .status(task.getStatus().name())
                .fileName(task.getFileName())
                .fileSize(task.getFileSize())
                .pdfCount(task.getPdfCount())
                .extractFields(task.getExtractFields())
                .priority(task.getPriority())
                .createdAt(task.getCreatedAt())
                .startedAt(task.getStartedAt())
                .completedAt(task.getCompletedAt())
                .errorMessage(task.getErrorMessage())
                .excelPath(task.getExcelPath())
                .build();
    }
}
