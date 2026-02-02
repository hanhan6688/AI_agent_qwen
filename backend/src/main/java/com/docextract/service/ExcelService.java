package com.docextract.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.apache.poi.ss.usermodel.*;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;
import java.util.Map;

@Slf4j
@Service
@RequiredArgsConstructor
public class ExcelService {

    private final ObjectMapper objectMapper;

    @Value("${app.storage.excel-path}")
    private String excelPath;

    public String generateExcel(String jsonData, String taskName) throws IOException {
        // 解析JSON数据
        List<Map<String, Object>> dataList;
        try {
            if (jsonData.startsWith("[")) {
                dataList = objectMapper.readValue(jsonData, new TypeReference<List<Map<String, Object>>>() {});
            } else {
                // 如果不是数组，包装成数组
                Map<String, Object> singleData = objectMapper.readValue(jsonData, new TypeReference<Map<String, Object>>() {});
                dataList = List.of(singleData);
            }
        } catch (Exception e) {
            log.error("解析JSON数据失败", e);
            throw new IOException("解析JSON数据失败: " + e.getMessage());
        }

        if (dataList.isEmpty()) {
            throw new IOException("没有提取到数据");
        }

        // 创建工作簿
        try (Workbook workbook = new XSSFWorkbook()) {
            Sheet sheet = workbook.createSheet("提取结果");

            // 创建表头样式
            CellStyle headerStyle = workbook.createCellStyle();
            Font headerFont = workbook.createFont();
            headerFont.setBold(true);
            headerStyle.setFont(headerFont);
            headerStyle.setFillForegroundColor(IndexedColors.GREY_25_PERCENT.getIndex());
            headerStyle.setFillPattern(FillPatternType.SOLID_FOREGROUND);
            headerStyle.setBorderBottom(BorderStyle.THIN);
            headerStyle.setBorderTop(BorderStyle.THIN);
            headerStyle.setBorderLeft(BorderStyle.THIN);
            headerStyle.setBorderRight(BorderStyle.THIN);

            // 创建数据样式
            CellStyle dataStyle = workbook.createCellStyle();
            dataStyle.setBorderBottom(BorderStyle.THIN);
            dataStyle.setBorderTop(BorderStyle.THIN);
            dataStyle.setBorderLeft(BorderStyle.THIN);
            dataStyle.setBorderRight(BorderStyle.THIN);

            // 创建表头
            Map<String, Object> firstRow = dataList.get(0);
            Row headerRow = sheet.createRow(0);
            int colIndex = 0;
            for (String key : firstRow.keySet()) {
                Cell cell = headerRow.createCell(colIndex++);
                cell.setCellValue(key);
                cell.setCellStyle(headerStyle);
            }

            // 填充数据
            int rowIndex = 1;
            for (Map<String, Object> dataMap : dataList) {
                Row row = sheet.createRow(rowIndex++);
                colIndex = 0;
                for (String key : firstRow.keySet()) {
                    Cell cell = row.createCell(colIndex++);
                    Object value = dataMap.get(key);
                    if (value != null) {
                        cell.setCellValue(value.toString());
                    }
                    cell.setCellStyle(dataStyle);
                }
            }

            // 自动调整列宽
            for (int i = 0; i < colIndex; i++) {
                sheet.autoSizeColumn(i);
                // 限制最大宽度
                int maxWidth = 50;
                if (sheet.getColumnWidth(i) > maxWidth * 256) {
                    sheet.setColumnWidth(i, maxWidth * 256);
                }
                // 设置最小宽度
                if (sheet.getColumnWidth(i) < 12 * 256) {
                    sheet.setColumnWidth(i, 12 * 256);
                }
            }

            // 生成文件名
            String fileName = taskName + "_" + System.currentTimeMillis() + ".xlsx";
            Path filePath = Paths.get(excelPath).resolve(fileName);

            // 写入文件
            try (FileOutputStream fos = new FileOutputStream(filePath.toFile())) {
                workbook.write(fos);
            }

            log.info("Excel文件生成成功: {}", filePath);
            return filePath.toString();
        }
    }
}
