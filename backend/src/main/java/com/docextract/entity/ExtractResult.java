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
@Table(name = "extract_results", indexes = {
    @Index(name = "idx_extract_results_task_id", columnList = "task_id")
})
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ExtractResult {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "task_id")
    private Long taskId;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "result_data", columnDefinition = "jsonb")
    private String resultData;

    @Column(name = "excel_path", length = 500)
    private String excelPath;

    @CreationTimestamp
    @Column(name = "created_at")
    private LocalDateTime createdAt;
}
