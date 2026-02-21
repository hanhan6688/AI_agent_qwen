package com.docextract.util;

import com.docextract.dto.Response;
import com.docextract.exception.ExtractException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.multipart.MaxUploadSizeExceededException;

import java.util.HashMap;
import java.util.Map;

@RestControllerAdvice
@Slf4j
public class GlobalExceptionHandler {

    @ExceptionHandler(Exception.class)
    @ResponseStatus(HttpStatus.INTERNAL_SERVER_ERROR)
    public Response<Void> handleException(Exception e) {
        log.error("系统异常", e);
        return Response.error("系统异常: " + e.getMessage());
    }

    @ExceptionHandler(RuntimeException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public Response<Void> handleRuntimeException(RuntimeException e) {
        log.error("运行时异常", e);
        return Response.error(e.getMessage());
    }

    // ========== 提取异常处理 ==========

    @ExceptionHandler(ExtractException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public Response<Void> handleExtractException(ExtractException e) {
        log.warn("提取异常: taskId={}, code={}, message={}",
                e.getTaskId(), e.getErrorCode(), e.getMessage());
        return Response.error(e.getMessage());
    }

    @ExceptionHandler(ExtractException.TaskNotFound.class)
    @ResponseStatus(HttpStatus.NOT_FOUND)
    public Response<Void> handleTaskNotFound(ExtractException.TaskNotFound e) {
        return Response.error(404, "任务不存在");
    }

    @ExceptionHandler(ExtractException.Timeout.class)
    @ResponseStatus(HttpStatus.REQUEST_TIMEOUT)
    public Response<Void> handleTimeout(ExtractException.Timeout e) {
        return Response.error(408, "任务处理超时，请稍后重试");
    }

    @ExceptionHandler(ExtractException.ConcurrencyLimit.class)
    @ResponseStatus(HttpStatus.TOO_MANY_REQUESTS)
    public Response<Void> handleConcurrencyLimit(ExtractException.ConcurrencyLimit e) {
        return Response.error(429, "系统繁忙，请稍后重试");
    }

    // ========== 其他异常处理 ==========

    @ExceptionHandler(MethodArgumentNotValidException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public Response<Map<String, String>> handleValidationException(MethodArgumentNotValidException e) {
        Map<String, String> errors = new HashMap<>();
        e.getBindingResult().getAllErrors().forEach(error -> {
            String fieldName = ((FieldError) error).getField();
            String errorMessage = error.getDefaultMessage();
            errors.put(fieldName, errorMessage);
        });
        return Response.error(400, "参数验证失败");
    }

    @ExceptionHandler(AccessDeniedException.class)
    @ResponseStatus(HttpStatus.FORBIDDEN)
    public Response<Void> handleAccessDeniedException(AccessDeniedException e) {
        log.error("访问拒绝", e);
        return Response.error(403, "访问拒绝");
    }

    @ExceptionHandler(MaxUploadSizeExceededException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public Response<Void> handleMaxUploadSizeExceededException(MaxUploadSizeExceededException e) {
        log.error("文件大小超过限制", e);
        return Response.error(400, "文件大小超过限制");
    }
}
