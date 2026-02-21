package com.docextract.entity;

import com.fasterxml.jackson.annotation.JsonFormat;
import jakarta.persistence.*;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.annotations.UpdateTimestamp;
import org.hibernate.type.SqlTypes;

import java.time.LocalDateTime;
import java.util.Map;

@Entity
@Table(name = "tasks")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Task {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "task_id")
    private Long taskId;

    @NotNull(message = "用户ID不能为空")
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id", nullable = false)
    private User user;

    @NotBlank(message = "任务名称不能为空")
    @Column(name = "task_name", nullable = false, length = 200)
    private String taskName;

    @Column(name = "document_count", nullable = false)
    @Builder.Default
    private Integer documentCount = 0;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "file_path", columnDefinition = "jsonb")
    private Map<String, String> filePath;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 20)
    @Builder.Default
    private TaskStatus status = TaskStatus.PENDING;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    @Column(name = "start_time")
    private LocalDateTime startTime;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    @Column(name = "end_time")
    private LocalDateTime endTime;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "result", columnDefinition = "jsonb")
    private Map<String, Object> result;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "extract_fields", columnDefinition = "jsonb")
    private Map<String, Object> extractFields;

    @Column(name = "error_message", length = 2000)
    private String errorMessage;

    /**
     * 当前处理阶段
     */
    @Column(name = "stage", length = 30)
    @Builder.Default
    private String stage = "PENDING";

    /**
     * 进度百分比 0-100
     */
    @Column(name = "progress")
    @Builder.Default
    private Integer progress = 0;

    /**
     * 重试次数
     */
    @Column(name = "retry_count")
    @Builder.Default
    private Integer retryCount = 0;

    /**
     * 处理详情（JSON格式存储中间结果）
     */
    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "processing_details", columnDefinition = "jsonb")
    private Map<String, Object> processingDetails;

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @UpdateTimestamp
    @Column(name = "updated_at")
    private LocalDateTime updatedAt;

    public enum TaskStatus {
        PENDING,       // 等待处理
        PROCESSING,    // 处理中
        COMPLETED,     // 已完成
        FAILED         // 失败
    }
}
