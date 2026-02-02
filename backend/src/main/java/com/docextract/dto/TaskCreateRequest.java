package com.docextract.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class TaskCreateRequest {

    @NotBlank(message = "任务名称不能为空")
    private String taskName;

    @NotNull(message = "用户ID不能为空")
    private Long userId;

    private String extractFields; // JSON字符串
}
