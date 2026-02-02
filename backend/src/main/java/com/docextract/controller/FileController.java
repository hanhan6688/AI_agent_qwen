package com.docextract.controller;

import com.docextract.dto.ApiResponse;
import com.docextract.service.FileStorageService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.io.FileSystemResource;
import org.springframework.core.io.Resource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;

@Slf4j
@RestController
@RequestMapping("/api/files")
@RequiredArgsConstructor
@CrossOrigin(origins = "*")
public class FileController {

    private final FileStorageService fileStorageService;

    @GetMapping("/download/excel/{taskId}")
    public ResponseEntity<Resource> downloadExcel(@PathVariable Long taskId, @RequestParam String fileName) {
        try {
            Path filePath = fileStorageService.getExcelPath(fileName);
            Resource resource = new FileSystemResource(filePath);

            if (!resource.exists()) {
                return ResponseEntity.notFound().build();
            }

            String contentType = Files.probeContentType(filePath);
            if (contentType == null) {
                contentType = "application/octet-stream";
            }

            return ResponseEntity.ok()
                    .contentType(MediaType.parseMediaType(contentType))
                    .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"" + fileName + "\"")
                    .body(resource);
        } catch (Exception e) {
            log.error("下载Excel文件失败", e);
            return ResponseEntity.internalServerError().build();
        }
    }

    @GetMapping("/download/upload/{fileName}")
    public ResponseEntity<Resource> downloadUploadedFile(@PathVariable String fileName) {
        try {
            Path filePath = fileStorageService.getFilePath(fileName);
            Resource resource = new FileSystemResource(filePath);

            if (!resource.exists()) {
                return ResponseEntity.notFound().build();
            }

            String contentType = Files.probeContentType(filePath);
            if (contentType == null) {
                contentType = "application/octet-stream";
            }

            return ResponseEntity.ok()
                    .contentType(MediaType.parseMediaType(contentType))
                    .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"" + fileName + "\"")
                    .body(resource);
        } catch (Exception e) {
            log.error("下载文件失败", e);
            return ResponseEntity.internalServerError().build();
        }
    }

    @GetMapping("/preview/upload/{fileName}")
    public ResponseEntity<Resource> previewUploadedFile(@PathVariable String fileName) {
        try {
            Path filePath = fileStorageService.getFilePath(fileName);
            Resource resource = new FileSystemResource(filePath);

            if (!resource.exists()) {
                return ResponseEntity.notFound().build();
            }

            String contentType = Files.probeContentType(filePath);
            if (contentType == null) {
                contentType = "application/octet-stream";
            }

            // 对于PDF文件，设置inline以便浏览器预览
            String disposition = contentType.equals("application/pdf") 
                ? "inline" 
                : "attachment";
            
            String encodedFileName = URLEncoder.encode(fileName, StandardCharsets.UTF_8.toString())
                .replace("+", "%20");

            return ResponseEntity.ok()
                    .contentType(MediaType.parseMediaType(contentType))
                    .header(HttpHeaders.CONTENT_DISPOSITION, 
                            disposition + "; filename*=UTF-8''" + encodedFileName)
                    .body(resource);
        } catch (Exception e) {
            log.error("预览文件失败", e);
            return ResponseEntity.internalServerError().build();
        }
    }
}
