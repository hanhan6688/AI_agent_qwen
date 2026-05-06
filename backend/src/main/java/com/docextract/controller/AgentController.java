package com.docextract.controller;

import com.docextract.dto.Response;
import com.docextract.service.AgentChatService;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.Map;

@RestController
@RequestMapping("/api/agent")
@RequiredArgsConstructor
@Slf4j
public class AgentController {

    private static final ObjectMapper OBJECT_MAPPER = new ObjectMapper();

    private final AgentChatService agentChatService;

    @GetMapping("/profile")
    public Response<Map<String, Object>> profile() {
        return Response.success(agentChatService.profile());
    }

    @PostMapping("/chat")
    public Response<Map<String, Object>> chat(@RequestBody Map<String, Object> request) {
        Object rawMessage = request.get("message");
        String message = rawMessage == null ? "" : String.valueOf(rawMessage).trim();
        if (message.isBlank()) {
            return Response.error(400, "消息不能为空");
        }

        Object history = request.get("history");
        Object rawMode = request.get("mode");
        String mode = rawMode == null ? "normal" : String.valueOf(rawMode).trim();
        Map<String, Object> reply = agentChatService.chat(message, history, mode);
        return Response.success("智能体回复成功", reply);
    }

    @PostMapping(
            value = "/chat/stream",
            consumes = MediaType.MULTIPART_FORM_DATA_VALUE,
            produces = MediaType.TEXT_EVENT_STREAM_VALUE
    )
    public SseEmitter chatStream(
            @RequestPart(value = "payload", required = false) MultipartFile payload,
            @RequestParam(value = "message", required = false) String message,
            @RequestParam(value = "history", required = false) String history,
            @RequestParam(value = "mode", defaultValue = "normal") String mode,
            @RequestParam(value = "files", required = false) MultipartFile[] files) {

        Map<String, Object> payloadMap = readPayload(payload);
        String rawMessage = payloadMap.containsKey("message")
                ? String.valueOf(payloadMap.getOrDefault("message", ""))
                : (message == null ? "" : message);
        String rawMode = payloadMap.containsKey("mode")
                ? String.valueOf(payloadMap.getOrDefault("mode", mode))
                : mode;
        String rawHistory = payloadMap.containsKey("history")
                ? toJson(payloadMap.get("history"))
                : history;

        String normalizedMessage = fixMultipartEncoding(rawMessage).trim();
        String normalizedHistory = fixMultipartEncoding(rawHistory);
        boolean hasFiles = files != null && files.length > 0;
        if (normalizedMessage.isBlank() && !hasFiles) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "消息或PDF附件不能为空");
        }

        SseEmitter emitter = new SseEmitter(600_000L);
        agentChatService.streamChat(normalizedMessage, normalizedHistory, rawMode, files, emitter);
        return emitter;
    }

    private Map<String, Object> readPayload(MultipartFile payload) {
        if (payload == null || payload.isEmpty()) {
            return Collections.emptyMap();
        }
        try {
            String json = new String(payload.getBytes(), StandardCharsets.UTF_8);
            return OBJECT_MAPPER.readValue(json, Map.class);
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "payload JSON 解析失败", e);
        }
    }

    private String toJson(Object value) {
        if (value == null) {
            return "[]";
        }
        if (value instanceof String stringValue) {
            return stringValue;
        }
        try {
            return OBJECT_MAPPER.writeValueAsString(value);
        } catch (Exception e) {
            return "[]";
        }
    }

    private String fixMultipartEncoding(String value) {
        if (value == null || value.isBlank()) {
            return value;
        }

        if (!(value.contains("\u00c3") || value.contains("\u00c2") || value.contains("\ufffd")
                || value.contains("è") || value.contains("ç") || value.contains("æ"))) {
            return value;
        }

        try {
            String repaired = new String(value.getBytes(StandardCharsets.ISO_8859_1), StandardCharsets.UTF_8);
            return countCjk(repaired) > countCjk(value) ? repaired : value;
        } catch (Exception ignored) {
            return value;
        }
    }

    private int countCjk(String value) {
        int count = 0;
        for (int i = 0; i < value.length(); i++) {
            char ch = value.charAt(i);
            if (ch >= '\u4e00' && ch <= '\u9fff') {
                count++;
            }
        }
        return count;
    }
}
