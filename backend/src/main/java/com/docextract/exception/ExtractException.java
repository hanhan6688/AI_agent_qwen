package com.docextract.exception;

/**
 * 提取异常
 */
public class ExtractException extends RuntimeException {

    private String errorCode;
    private Long taskId;

    public ExtractException(String message) {
        super(message);
    }

    public ExtractException(String message, Throwable cause) {
        super(message, cause);
    }

    public ExtractException(String errorCode, String message) {
        super(message);
        this.errorCode = errorCode;
    }

    public ExtractException(Long taskId, String message) {
        super(message);
        this.taskId = taskId;
    }

    public ExtractException(Long taskId, String errorCode, String message) {
        super(message);
        this.taskId = taskId;
        this.errorCode = errorCode;
    }

    public String getErrorCode() {
        return errorCode;
    }

    public Long getTaskId() {
        return taskId;
    }

    /**
     * 任务不存在异常
     */
    public static class TaskNotFound extends ExtractException {
        public TaskNotFound(Long taskId) {
            super(taskId, "TASK_NOT_FOUND", "任务不存在: " + taskId);
        }
    }

    /**
     * 任务处理超时异常
     */
    public static class Timeout extends ExtractException {
        public Timeout(Long taskId, int timeoutSeconds) {
            super(taskId, "TIMEOUT", "任务处理超时: " + timeoutSeconds + "秒");
        }
    }

    /**
     * 重试次数超限异常
     */
    public static class RetryLimitExceeded extends ExtractException {
        public RetryLimitExceeded(Long taskId, int maxRetries) {
            super(taskId, "RETRY_LIMIT", "已达到最大重试次数: " + maxRetries);
        }
    }

    /**
     * 并发限制异常
     */
    public static class ConcurrencyLimit extends ExtractException {
        public ConcurrencyLimit(String message) {
            super("CONCURRENCY_LIMIT", message);
        }
    }

    /**
     * Python脚本执行异常
     */
    public static class ScriptExecution extends ExtractException {
        public ScriptExecution(Long taskId, String message) {
            super(taskId, "SCRIPT_ERROR", message);
        }
    }
}
