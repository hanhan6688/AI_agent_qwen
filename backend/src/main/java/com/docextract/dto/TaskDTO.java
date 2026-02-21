package com.docextract.dto;

import com.docextract.entity.Task;
import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.Map;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class TaskDTO {
    private Long taskId;
    private Long userId;
    private String username;
    private String taskName;
    private Integer documentCount;
    private Map<String, String> filePath;
    private String status;
    private String statusText;

    /**
     * 当前处理阶段
     */
    private String stage;

    /**
     * 进度百分比
     */
    private Integer progress;

    /**
     * 重试次数
     */
    private Integer retryCount;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime startTime;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime endTime;
    private Map<String, Object> result;
    private Map<String, Object> extractFields;
    private Map<String, Object> processingDetails;
    private String errorMessage;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
