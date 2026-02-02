package com.docextract.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.LocalDateTime;

@Entity
@Table(name = "tasks", indexes = {
    @Index(name = "idx_tasks_user_status", columnList = "user_id, status"),
    @Index(name = "idx_tasks_created_at", columnList = "created_at DESC"),
    @Index(name = "idx_tasks_status", columnList = "status")
})
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class Task {

    @Id
    @Column(name = "task_id", length = 100, nullable = false, unique = true)
    private String taskId;

    @Column(name = "user_id")
    private Long userId;

    @Column(name = "batch_id", length = 100)
    private String batchId;

    @Column(name = "task_name")
    private String taskName;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private TaskStatus status = TaskStatus.PENDING;

    @Column(name = "file_path", length = 500)
    private String filePath;
    @Column(name = "excel_path", length = 500)
    private String excelPath;
    @Column(name = "file_name", length = 255)
    private String fileName;

    @Column(name = "file_size")
    private Long fileSize;

    @Column(name = "pdf_count")
    private Integer pdfCount = 0;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "extract_fields", columnDefinition = "jsonb")
    private String extractFields;

    private Integer priority = 5;

    @CreationTimestamp
    @Column(name = "created_at")
    private LocalDateTime createdAt;

    @Column(name = "started_at")
    private LocalDateTime startedAt;

    @Column(name = "completed_at")
    private LocalDateTime completedAt;

    @Column(name = "error_message", columnDefinition = "text")
    private String errorMessage;

    public enum TaskStatus {
        PENDING,
        PROCESSING,
        COMPLETED,
        FAILED
    }
}
