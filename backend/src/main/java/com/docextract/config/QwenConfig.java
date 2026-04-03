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

    /**
     * 默认温度参数
     */
    private double defaultTemperature = 0.1D;

    /**
     * 默认 top-p 参数
     */
    private double defaultTopP = 0.9D;

    /**
     * 默认 top-k 参数
     */
    private int defaultTopK = 20;

    /**
     * 默认最大输出 token 数
     */
    private int defaultMaxTokens = 2048;

    /**
     * 默认重复惩罚
     */
    private double defaultRepetitionPenalty = 1.0D;

    /**
     * 默认请求超时（秒）
     */
    private int defaultRequestTimeout = 600;

    /**
     * 本地模型默认服务地址
     */
    private String localBaseUrl = "http://127.0.0.1:8000/v1";

    /**
     * 本地模型默认 API Key
     */
    private String localApiKey = "EMPTY";

    /**
     * 本地模型默认名称
     */
    private String localModel = "Qwen/Qwen2.5-VL-7B-Instruct";

    /**
     * 本地模型服务类型
     */
    private String localProvider = "openai-compatible";

    /**
     * 本地模型是否支持视觉输入
     */
    private boolean localVisionEnabled = true;
}
