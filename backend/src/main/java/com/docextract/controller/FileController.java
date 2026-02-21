package com.docextract.controller;

import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.FileSystemResource;
import org.springframework.core.io.Resource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

@RestController
@RequestMapping("/api/files")
@RequiredArgsConstructor
@Slf4j
public class FileController {

    @Value("${file.upload-dir}")
    private String uploadDir;

    @Value("${file.output-dir}")
    private String outputDir;

    @Value("${file.data-dir:${user.home}/docextract/data}")
    private String dataDir;

    @GetMapping("/download/upload/{fileName}")
    public void downloadUploadedFile(
            @PathVariable String fileName,
            HttpServletResponse response) throws IOException {

        Path filePath = Paths.get(uploadDir, fileName);
        if (!Files.exists(filePath)) {
            response.setStatus(HttpStatus.NOT_FOUND.value());
            return;
        }

        Resource resource = new FileSystemResource(filePath);

        response.setContentType(MediaType.APPLICATION_OCTET_STREAM_VALUE);
        response.setHeader(HttpHeaders.CONTENT_DISPOSITION,
                "attachment; filename=\"" + fileName + "\"");

        Files.copy(filePath, response.getOutputStream());
        response.getOutputStream().flush();
    }

    @GetMapping("/preview/upload/{fileName}")
    public ResponseEntity<Resource> previewUploadedFile(@PathVariable String fileName) {
        try {
            Path filePath = Paths.get(uploadDir, fileName);
            if (!Files.exists(filePath)) {
                return ResponseEntity.notFound().build();
            }

            Resource resource = new FileSystemResource(filePath);
            String contentType = Files.probeContentType(filePath);
            if (contentType == null) {
                contentType = MediaType.APPLICATION_OCTET_STREAM_VALUE;
            }

            return ResponseEntity.ok()
                    .contentType(MediaType.parseMediaType(contentType))
                    .header(HttpHeaders.CONTENT_DISPOSITION,
                            "inline; filename=\"" + fileName + "\"")
                    .body(resource);

        } catch (IOException e) {
            log.error("文件预览失败: {}", fileName, e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).build();
        }
    }

    @GetMapping("/download/excel/{taskId}")
    public void downloadExcel(
            @PathVariable Long taskId,
            @RequestParam String fileName,
            HttpServletResponse response) throws IOException {

        Path filePath = Paths.get(outputDir, taskId.toString(), fileName);
        if (!Files.exists(filePath)) {
            response.setStatus(HttpStatus.NOT_FOUND.value());
            return;
        }

        Resource resource = new FileSystemResource(filePath);

        response.setContentType(MediaType.APPLICATION_OCTET_STREAM_VALUE);
        response.setHeader(HttpHeaders.CONTENT_DISPOSITION,
                "attachment; filename=\"" + fileName + "\"");

        Files.copy(filePath, response.getOutputStream());
        response.getOutputStream().flush();
    }

    /**
     * 下载任务结果文件（仅支持ZIP）
     * 路径示例: /api/files/download/result/taskName/result/taskName.zip
     */
    @GetMapping("/download/result/{taskName}/result/{fileName}")
    public void downloadResultFile(
            @PathVariable String taskName,
            @PathVariable String fileName,
            HttpServletResponse response) throws IOException {

        // 清理任务名称
        String safeTaskName = taskName.replaceAll("[^a-zA-Z0-9\\u4e00-\\u9fa5_-]", "_");
        Path filePath = Paths.get(dataDir, safeTaskName, "result", fileName);
        
        log.info("下载结果文件: {}", filePath);
        
        if (!Files.exists(filePath)) {
            response.setStatus(HttpStatus.NOT_FOUND.value());
            response.getWriter().write("{\"error\":\"文件不存在\"}");
            return;
        }

        // 只支持zip文件下载
        if (!fileName.endsWith(".zip")) {
            response.setStatus(HttpStatus.BAD_REQUEST.value());
            response.getWriter().write("{\"error\":\"仅支持下载ZIP文件\"}");
            return;
        }

        response.setContentType("application/zip");
        response.setHeader(HttpHeaders.CONTENT_DISPOSITION,
                "attachment; filename=\"" + fileName + "\"");

        Files.copy(filePath, response.getOutputStream());
        response.getOutputStream().flush();
    }

    /**
     * 下载任务目录下的JSON文件
     */
    @GetMapping("/download/json/{taskName}/{fileName}")
    public void downloadJsonFile(
            @PathVariable String taskName,
            @PathVariable String fileName,
            HttpServletResponse response) throws IOException {

        String safeTaskName = taskName.replaceAll("[^a-zA-Z0-9\\u4e00-\\u9fa5_-]", "_");
        Path filePath = Paths.get(dataDir, safeTaskName, "json_data", fileName);
        
        if (!Files.exists(filePath)) {
            response.setStatus(HttpStatus.NOT_FOUND.value());
            return;
        }

        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.setHeader(HttpHeaders.CONTENT_DISPOSITION,
                "attachment; filename=\"" + fileName + "\"");

        Files.copy(filePath, response.getOutputStream());
        response.getOutputStream().flush();
    }
}
