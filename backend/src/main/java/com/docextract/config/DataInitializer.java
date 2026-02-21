package com.docextract.config;

import com.docextract.entity.User;
import com.docextract.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
@Slf4j
public class DataInitializer implements CommandLineRunner {

    private final UserRepository userRepository;

    @Override
    public void run(String... args) {
        // 创建默认admin账户
        if (!userRepository.existsByUsername("admin")) {
            User admin = User.builder()
                    .username("admin")
                    .password("admin123")  // 明文密码
                    .email("admin@example.com")
                    .documentCount(0)
                    .build();
            userRepository.save(admin);
            log.info("默认管理员账户已创建: admin / admin123");
        }
    }
}
