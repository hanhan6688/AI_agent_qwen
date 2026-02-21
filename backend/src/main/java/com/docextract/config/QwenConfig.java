package com.docextract.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

/**
 * Qwen智能提取配置
 */
@Data
@Configuration
@ConfigurationProperties(prefix = "qwen")
public class QwenConfig {

    /**
     * API密钥
     */
    private String apiKey;

    /**
     * 模型名称
     */
    private String model = "qwen-vl-max-latest";

    /**
     * 最大并发处理数
     */
    private int maxConcurrent = 3;

    /**
     * 单个任务超时时间（秒）
     */
    private int taskTimeout = 600;

    /**
     * 最大重试次数
     */
    private int maxRetries = 3;

    /**
     * 重试间隔（秒）
     */
    private int retryInterval = 5;

    /**
     * TPM限制
     */
    private int maxTpm = 1000000;

    /**
     * 单次最大图片数
     */
    private int maxImages = 15;

    /**
     * 最大上下文长度
     */
    private int maxContextLength = 150000;
}
