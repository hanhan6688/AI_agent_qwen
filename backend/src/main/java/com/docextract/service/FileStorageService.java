package com.docextract.service;

import jakarta.annotation.PostConstruct;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.util.UUID;

@Slf4j
@Service
public class FileStorageService {

    @Value("${app.storage.upload-path}")
    private String uploadPath;

    @Value("${app.storage.processed-path}")
    private String processedPath;

    @Value("${app.storage.excel-path}")
    private String excelPath;

    @PostConstruct
    public void init() {
        try {
            Files.createDirectories(Paths.get(uploadPath));
            Files.createDirectories(Paths.get(processedPath));
            Files.createDirectories(Paths.get(excelPath));
            log.info("文件存储目录初始化完成");
        } catch (IOException e) {
            log.error("初始化文件存储目录失败", e);
            throw new RuntimeException("初始化文件存储目录失败", e);
        }
    }

    public String storeFile(MultipartFile file) throws IOException {
        String originalFilename = file.getOriginalFilename();
        String extension = originalFilename != null && originalFilename.contains(".")
                ? originalFilename.substring(originalFilename.lastIndexOf("."))
                : "";
        String fileName = UUID.randomUUID().toString() + extension;

        Path targetLocation = Paths.get(uploadPath).resolve(fileName);
        Files.copy(file.getInputStream(), targetLocation, StandardCopyOption.REPLACE_EXISTING);

        log.info("文件保存成功: {}", targetLocation);

        return targetLocation.toString();
    }

    public Path getFilePath(String fileName) {
        return Paths.get(uploadPath).resolve(fileName);
    }

    public Path getExcelPath(String fileName) {
        return Paths.get(excelPath).resolve(fileName);
    }

    public String getUploadPath() {
        return uploadPath;
    }

    public String getProcessedPath() {
        return processedPath;
    }

    public String getExcelPath() {
        return excelPath;
    }
}
