package com.docextract.repository;

import com.docextract.entity.Task;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface TaskRepository extends JpaRepository<Task, String> {

    List<Task> findByUserId(Long userId);

    Page<Task> findByUserIdOrderByCreatedAtDesc(Long userId, Pageable pageable);

    Page<Task> findByUserIdAndStatus(Long userId, Task.TaskStatus status, Pageable pageable);

    List<Task> findByStatus(Task.TaskStatus status);

    long countByUserIdAndStatus(Long userId, Task.TaskStatus status);

    List<Task> findByBatchId(String batchId);
}
