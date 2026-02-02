package com.docextract.repository;

import com.docextract.entity.ExtractResult;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;

@Repository
public interface ExtractResultRepository extends JpaRepository<ExtractResult, Long> {

    Optional<ExtractResult> findByTaskId(Long taskId);

    void deleteByTaskId(Long taskId);
}
