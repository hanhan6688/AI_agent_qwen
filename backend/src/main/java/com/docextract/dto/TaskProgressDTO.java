package com.docextract.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 任务进度DTO
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class TaskProgressDTO {

    private Long taskId;

    /**
     * 当前阶段: UPLOADING, OCR_PROCESSING, QWEN_EXTRACTING, COMPLETED, FAILED
     */
    private String stage;

    /**
     * 阶段描述
     */
    private String stageText;

    /**
     * 进度百分比 0-100
     */
    private int progress;

    /**
     * 当前处理文件名
     */
    private String currentFile;

    /**
     * 已处理文件数
     */
    private int processedCount;

    /**
     * 总文件数
     */
    private int totalCount;

    /**
     * 预计剩余时间（秒）
     */
    private Long estimatedTimeRemaining;

    /**
     * 错误信息
     */
    private String errorMessage;

    public static TaskProgressDTO of(Long taskId, String stage, int progress) {
        return TaskProgressDTO.builder()
                .taskId(taskId)
                .stage(stage)
                .stageText(getStageText(stage))
                .progress(progress)
                .build();
    }

    private static String getStageText(String stage) {
        return switch (stage) {
            case "UPLOADING" -> "上传文件中";
            case "OCR_PROCESSING" -> "OCR识别中";
            case "QWEN_EXTRACTING" -> "AI提取中";
            case "COMPLETED" -> "处理完成";
            case "FAILED" -> "处理失败";
            default -> "处理中";
        };
    }
}
