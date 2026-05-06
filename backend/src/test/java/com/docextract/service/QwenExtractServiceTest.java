package com.docextract.service;

import com.docextract.config.QwenConfig;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.test.util.ReflectionTestUtils;

import java.nio.file.Path;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;

@ExtendWith(MockitoExtension.class)
class QwenExtractServiceTest {

    @Mock
    private QwenConfig qwenConfig;

    @Mock
    private RedisTemplate<String, Object> redisTemplate;

    private QwenExtractService qwenExtractService;

    @BeforeEach
    void setUp() {
        qwenExtractService = new QwenExtractService(qwenConfig, redisTemplate, new ObjectMapper());
        ReflectionTestUtils.setField(qwenExtractService, "pythonPath", "python");
        ReflectionTestUtils.setField(qwenExtractService, "scriptPath", "integrated_processor.py");
    }

    @Test
    void parseInferenceConfigShouldUseTemperatureZeroByDefault() {
        Map<String, Object> config = ReflectionTestUtils.invokeMethod(
                qwenExtractService,
                "parseInferenceConfig",
                (String) null
        );

        assertEquals(0, config.get("temperature"));
        assertEquals(1, config.get("topP"));
        assertEquals(1, config.get("topK"));
        assertEquals(4096, config.get("maxTokens"));
    }

    @Test
    void parseInferenceConfigShouldMergeUserOverridesIntoDefaults() {
        Map<String, Object> config = ReflectionTestUtils.invokeMethod(
                qwenExtractService,
                "parseInferenceConfig",
                "{\"topK\":8,\"temperature\":0.3}"
        );

        assertEquals(0.3, config.get("temperature"));
        assertEquals(8, config.get("topK"));
        assertEquals(1, config.get("topP"));
    }

    @Test
    void extractPythonFailureDetailShouldPreferJsonMessageFromStdout() {
        String detail = ReflectionTestUtils.invokeMethod(
                qwenExtractService,
                "extractPythonFailureDetail",
                "{\"status\":\"error\",\"message\":\"DASHSCOPE_API_KEY环境变量未设置\"}",
                "2026-04-29 22:28:35,991 - INFO - 已加载模型路由缓存: 4 条记录"
        );

        assertEquals("DASHSCOPE_API_KEY环境变量未设置", detail);
    }

    @Test
    void buildCommandShouldOnlyPassInputFileToPython() {
        List<String> command = ReflectionTestUtils.invokeMethod(
                qwenExtractService,
                "buildCommand",
                Path.of("C:\\temp\\input_111.json")
        );

        assertEquals(3, command.size());
        assertEquals("python", command.get(0));
        assertEquals("integrated_processor.py", command.get(1));
        assertEquals("C:\\temp\\input_111.json", command.get(2));
    }
}
