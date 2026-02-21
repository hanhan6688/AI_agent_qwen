package com.docextract.repository;

import com.docextract.entity.User;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

import java.util.Optional;

@Repository
public interface UserRepository extends JpaRepository<User, Long> {

    Optional<User> findByUsername(String username);

    Optional<User> findByEmail(String email);

    @Query("SELECT u.documentCount FROM User u WHERE u.userId = :userId")
    Integer getDocumentCountByUserId(Long userId);

    boolean existsByUsername(String username);

    boolean existsByEmail(String email);
}
