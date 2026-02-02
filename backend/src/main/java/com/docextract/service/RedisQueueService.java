package com.docextract.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;

import java.util.concurrent.TimeUnit;

@Slf4j
@Service
@RequiredArgsConstructor
public class RedisQueueService {

    private final RedisTemplate<String, Object> redisTemplate;

    @Value("${app.queue.pending}")
    private String pendingQueue;

    @Value("${app.queue.processing}")
    private String processingQueue;

    public void addToPendingQueue(String taskId) {
        redisTemplate.opsForList().rightPush(pendingQueue, taskId);
        log.info("任务 {} 加入待处理队列", taskId);
    }

    public String getNextPendingTask() {
        String taskId = (String) redisTemplate.opsForList().leftPop(pendingQueue);
        if (taskId != null) {
            addToProcessingQueue(taskId);
        }
        return taskId;
    }

    private void addToProcessingQueue(String taskId) {
        redisTemplate.opsForHash().put(processingQueue, taskId, String.valueOf(System.currentTimeMillis()));
        // 设置任务处理超时时间（30分钟）
        redisTemplate.expire(processingQueue, 30, TimeUnit.MINUTES);
        log.info("任务 {} 加入处理中队列", taskId);
    }

    public boolean isTaskProcessing(String taskId) {
        return redisTemplate.opsForHash().hasKey(processingQueue, taskId);
    }

    public Long getQueueSize(String queueName) {
        return redisTemplate.opsForList().size(queueName);
    }

    public boolean isTaskProcessing(Long taskId) {
        return redisTemplate.opsForHash().hasKey(processingQueue, taskId.toString());
    }
}
