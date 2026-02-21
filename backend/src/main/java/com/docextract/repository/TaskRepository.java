package com.docextract.repository;

import com.docextract.entity.Task;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface TaskRepository extends JpaRepository<Task, Long> {

    Page<Task> findByUserUserIdOrderByCreatedAtDesc(Long userId, Pageable pageable);

    List<Task> findByUserUserIdAndStatus(Long userId, Task.TaskStatus status);

    Optional<Task> findByTaskId(Long taskId);

    @Query("SELECT t FROM Task t WHERE t.user.userId = :userId AND t.taskName LIKE %:keyword% ORDER BY t.createdAt DESC")
    Page<Task> searchTasks(@Param("userId") Long userId, @Param("keyword") String keyword, Pageable pageable);

    @Query("SELECT t FROM Task t WHERE t.status IN :statuses")
    List<Task> findByStatuses(@Param("statuses") List<Task.TaskStatus> statuses);

    @Query("SELECT COUNT(t) FROM Task t WHERE t.user.userId = :userId")
    Long countByUserId(Long userId);

    /**
     * 统计用户活跃任务数
     */
    long countByUserUserIdAndStatusIn(Long userId, List<Task.TaskStatus> statuses);

    /**
     * 按任务名称查询
     */
    List<Task> findByTaskNameOrderByCreatedAtDesc(String taskName);

    /**
     * 按用户ID和任务名称查询
     */
    List<Task> findByUserUserIdAndTaskNameOrderByCreatedAtDesc(Long userId, String taskName);

    /**
     * 获取用户所有不重复的任务名称
     */
    @Query("SELECT DISTINCT t.taskName FROM Task t WHERE t.user.userId = :userId ORDER BY t.taskName")
    List<String> findDistinctTaskNamesByUserId(@Param("userId") Long userId);

    /**
     * 获取用户某个任务名称下的所有任务
     */
    @Query("SELECT t FROM Task t WHERE t.user.userId = :userId AND t.taskName = :taskName ORDER BY t.createdAt DESC")
    List<Task> findByUserIdAndTaskName(@Param("userId") Long userId, @Param("taskName") String taskName);

    /**
     * 获取用户所有任务
     */
    List<Task> findByUserUserIdOrderByCreatedAtDesc(Long userId);
}
