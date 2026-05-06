package com.docextract.controller;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.core.io.Resource;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.test.util.ReflectionTestUtils;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class FileControllerTest {

    @TempDir
    Path tempDir;

    private FileController fileController;

    @BeforeEach
    void setUp() {
        fileController = new FileController();
        ReflectionTestUtils.setField(fileController, "uploadDir", tempDir.resolve("uploads").toString());
        ReflectionTestUtils.setField(fileController, "outputDir", tempDir.resolve("outputs").toString());
        ReflectionTestUtils.setField(fileController, "dataDir", tempDir.resolve("data").toString());
    }

    @Test
    void previewTaskPdfFileShouldReturnPdfResource() throws Exception {
        Path pdfPath = tempDir.resolve("data").resolve("task_demo").resolve("pdf");
        Files.createDirectories(pdfPath);
        Path file = pdfPath.resolve("demo.pdf");
        Files.writeString(file, "pdf-content", StandardCharsets.UTF_8);

        ResponseEntity<Resource> response = fileController.previewTaskPdfFile("task demo", "demo.pdf");

        assertEquals(HttpStatus.OK, response.getStatusCode());
        assertNotNull(response.getBody());
        assertTrue(response.getHeaders().getContentType().toString().contains("application/pdf"));
    }

    @Test
    void downloadResultFileShouldRejectNonZipFiles() throws Exception {
        Path resultDir = tempDir.resolve("data").resolve("task_demo").resolve("result");
        Files.createDirectories(resultDir);
        Files.writeString(resultDir.resolve("bad.txt"), "not-zip", StandardCharsets.UTF_8);

        MockHttpServletResponse response = new MockHttpServletResponse();
        fileController.downloadResultFile("task demo", "bad.txt", response);

        assertEquals(400, response.getStatus());
        assertTrue(response.getContentAsString().isEmpty() || response.getContentAsString().contains("ZIP"));
    }

    @Test
    void downloadResultFileShouldStreamZipFile() throws Exception {
        Path resultDir = tempDir.resolve("data").resolve("task_demo").resolve("result");
        Files.createDirectories(resultDir);
        Path zipPath = resultDir.resolve("task_demo.zip");
        try (ZipOutputStream zos = new ZipOutputStream(Files.newOutputStream(zipPath))) {
            zos.putNextEntry(new ZipEntry("a.json"));
            zos.write("{\"ok\":true}".getBytes(StandardCharsets.UTF_8));
            zos.closeEntry();
        }

        MockHttpServletResponse response = new MockHttpServletResponse();
        fileController.downloadResultFile("task demo", "task_demo.zip", response);

        assertEquals(200, response.getStatus());
        assertEquals("application/zip", response.getContentType());
        assertTrue(response.getContentAsByteArray().length > 0);
    }
}
