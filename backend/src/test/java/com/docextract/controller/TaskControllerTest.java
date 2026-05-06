package com.docextract.controller;

import com.docextract.dto.TaskDTO;
import com.docextract.dto.TaskProgressDTO;
import com.docextract.service.TaskService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;
import java.util.Map;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(TaskController.class)
@AutoConfigureMockMvc(addFilters = false)
class TaskControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private TaskService taskService;

    @Test
    void createTaskShouldRejectWhenActiveTaskCountTooHigh() throws Exception {
        MockMultipartFile file = new MockMultipartFile(
                "files",
                "paper.pdf",
                "application/pdf",
                "fake-pdf".getBytes()
        );

        when(taskService.getActiveTaskCount(1L)).thenReturn(10L);

        mockMvc.perform(multipart("/api/tasks")
                        .file(file)
                        .param("taskName", "stress-task")
                        .param("extractFields", "[]")
                        .param("userId", "1")
                        .param("modelMode", "normal"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(500))
                .andExpect(jsonPath("$.message").value("您有太多正在处理的任务，请稍后再试"));
    }

    @Test
    void createJsonZipShouldReturnSanitizedDownloadUrl() throws Exception {
        when(taskService.createJsonZip("task 01/测试"))
                .thenReturn("C:/tmp/task_01_测试/result/task_01_测试.zip");

        mockMvc.perform(post("/api/tasks/create-json-zip")
                        .param("taskName", "task 01/测试"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.fileName").value("task_01_测试.zip"))
                .andExpect(jsonPath("$.data.downloadUrl").value("/api/files/download/result/task_01_测试/result/task_01_测试.zip"));
    }

    @Test
    void getTaskStatusShouldReturnStatusAndProgress() throws Exception {
        TaskDTO task = TaskDTO.builder()
                .taskId(8L)
                .status("PROCESSING")
                .statusText("处理中")
                .build();
        TaskProgressDTO progress = TaskProgressDTO.builder()
                .taskId(8L)
                .stage("QWEN_EXTRACTING")
                .stageText("AI提取中")
                .progress(66)
                .build();

        when(taskService.getTaskById(8L)).thenReturn(task);
        when(taskService.getTaskProgress(8L)).thenReturn(progress);

        mockMvc.perform(get("/api/tasks/8/status"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.status").value("PROCESSING"))
                .andExpect(jsonPath("$.data.statusText").value("处理中"))
                .andExpect(jsonPath("$.data.progress.progress").value(66))
                .andExpect(jsonPath("$.data.progress.stage").value("QWEN_EXTRACTING"));
    }

    @Test
    void getBatchTasksShouldReturnPayloadFromService() throws Exception {
        Map<String, Object> batch = Map.of(
                "taskName", "batch-a",
                "totalCount", 2,
                "status", "COMPLETED",
                "files", List.of(Map.of("taskId", 1, "fileName", "a.pdf"))
        );
        when(taskService.getBatchTasks(1L)).thenReturn(List.of(batch));

        mockMvc.perform(get("/api/tasks/batch").param("userId", "1"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data[0].taskName").value("batch-a"))
                .andExpect(jsonPath("$.data[0].totalCount").value(2))
                .andExpect(jsonPath("$.data[0].status").value("COMPLETED"));
    }
}
