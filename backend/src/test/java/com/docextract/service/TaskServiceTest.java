package com.docextract.service;

import com.docextract.config.QwenConfig;
import com.docextract.dto.TaskDTO;
import com.docextract.entity.Task;
import com.docextract.entity.User;
import com.docextract.repository.TaskRepository;
import com.docextract.repository.UserRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;
import org.mockito.junit.jupiter.MockitoExtension;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.core.ValueOperations;
import org.springframework.test.util.ReflectionTestUtils;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import java.util.Optional;
import java.util.zip.ZipInputStream;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class TaskServiceTest {

    @TempDir
    Path tempDir;

    @Mock
    private TaskRepository taskRepository;

    @Mock
    private UserRepository userRepository;

    @Mock
    private QwenExtractService qwenExtractService;

    @Mock
    private QwenConfig qwenConfig;

    @Mock
    private RedisTemplate<String, Object> redisTemplate;

    @Mock
    private ValueOperations<String, Object> valueOperations;

    private TaskService taskService;

    @BeforeEach
    void setUp() {
        MockitoAnnotations.openMocks(this);
        taskService = new TaskService(taskRepository, userRepository, qwenExtractService, qwenConfig, redisTemplate);
        ReflectionTestUtils.setField(taskService, "dataDir", tempDir.toString());
        ReflectionTestUtils.setField(taskService, "uploadDir", tempDir.resolve("uploads").toString());
        ReflectionTestUtils.setField(taskService, "outputDir", tempDir.resolve("outputs").toString());
        ReflectionTestUtils.setField(taskService, "batchTaskExecutor", (java.util.concurrent.Executor) Runnable::run);
    }

    @Test
    void getTaskPathsShouldSanitizeUnsafeTaskName() {
        String taskName = "task 01/测试";

        String dataDir = taskService.getTaskDataDir(taskName);
        String zipPath = taskService.getJsonZipPath(taskName);

        assertTrue(dataDir.endsWith("task_01_测试"));
        assertTrue(zipPath.endsWith("task_01_测试\\result\\task_01_测试.zip"));
    }

    @Test
    void createJsonZipShouldPackageJsonFiles() throws Exception {
        Path jsonDir = tempDir.resolve("task_01_测试").resolve("json_data");
        Files.createDirectories(jsonDir);
        Files.writeString(jsonDir.resolve("a.json"), "{\"a\":1}", StandardCharsets.UTF_8);
        Files.writeString(jsonDir.resolve("b.json"), "{\"b\":2}", StandardCharsets.UTF_8);

        String zipPath = taskService.createJsonZip("task 01/测试");

        Path resultZip = Path.of(zipPath);
        assertTrue(Files.exists(resultZip));

        int entryCount = 0;
        try (InputStream inputStream = Files.newInputStream(resultZip);
             ZipInputStream zis = new ZipInputStream(inputStream)) {
            while (zis.getNextEntry() != null) {
                entryCount++;
            }
        }
        assertEquals(2, entryCount);
    }

    @Test
    void createJsonZipShouldFailWhenJsonDirectoryMissing() {
        RuntimeException exception = assertThrows(RuntimeException.class,
                () -> taskService.createJsonZip("missing-task"));

        assertTrue(exception.getMessage().contains("JSON数据目录不存在"));
    }
    @Test
    void buildExtractFieldsPayloadShouldWrapFieldList() {
        Map<String, Object> payload = ReflectionTestUtils.invokeMethod(
                taskService,
                "buildExtractFieldsPayload",
                "[{\"name\":\"标题\",\"description\":\"论文标题\"}]"
        );

        assertTrue(payload.containsKey("fields"));
        assertEquals(1, ((java.util.List<?>) payload.get("fields")).size());
    }

    @Test
    void retryTaskShouldReusePreviousModelModeAndInferenceConfig() {
        String extractFieldsJson = "[{\"name\":\"标题\",\"description\":\"论文标题\"}]";
        String inferenceConfigJson = "{\"temperature\":0.2,\"topK\":8}";

        Task task = Task.builder()
                .taskId(9L)
                .user(User.builder().userId(1L).username("tester").build())
                .taskName("demo-task")
                .status(Task.TaskStatus.FAILED)
                .retryCount(0)
                .processingDetails(Map.of(
                        "requestedModelMode", "pro",
                        "requestedInferenceConfigJson", inferenceConfigJson
                ))
                .build();

        when(taskRepository.findById(9L)).thenReturn(Optional.of(task));
        when(taskRepository.save(any(Task.class))).thenAnswer(invocation -> invocation.getArgument(0));
        when(qwenConfig.getMaxRetries()).thenReturn(3);
        when(qwenExtractService.processTask(any(Task.class), eq(extractFieldsJson), eq("pro"), eq(inferenceConfigJson)))
                .thenReturn(Map.of(
                        "status", "success",
                        "model", "qwen3.6-plus",
                        "confidence", 0.91,
                        "data", Map.of("标题", "示例论文")
                ));

        TaskDTO retriedTask = taskService.retryTask(9L, extractFieldsJson);

        assertEquals("COMPLETED", retriedTask.getStatus());
        assertEquals("pro", task.getProcessingDetails().get("requestedModelMode"));
        assertEquals(inferenceConfigJson, task.getProcessingDetails().get("requestedInferenceConfigJson"));
        verify(qwenExtractService).processTask(any(Task.class), eq(extractFieldsJson), eq("pro"), eq(inferenceConfigJson));
    }
}
