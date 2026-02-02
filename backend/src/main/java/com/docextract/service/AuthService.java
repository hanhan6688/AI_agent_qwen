package com.docextract.service;

import com.docextract.dto.LoginRequest;
import com.docextract.dto.LoginResponse;
import com.docextract.entity.User;
import com.docextract.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;

@Slf4j
@Service
@RequiredArgsConstructor
public class AuthService {

    private final UserRepository userRepository;
    private final BCryptPasswordEncoder passwordEncoder = new BCryptPasswordEncoder();

    public LoginResponse login(LoginRequest request) {
        log.info("用户登录: {}", request.getUsername());

        User user = userRepository.findByUsername(request.getUsername())
                .orElseThrow(() -> new RuntimeException("用户名或密码错误"));

        if (!user.getActive()) {
            throw new RuntimeException("账号已被禁用");
        }

        // 临时修改：使用明文密码比较
        if (!request.getPassword().equals(user.getPassword())) {
            throw new RuntimeException("用户名或密码错误");
        }

        // 更新最后登录时间
        user.setLastLogin(LocalDateTime.now());
        userRepository.save(user);

        log.info("用户 {} 登录成功", user.getUsername());

        return LoginResponse.builder()
                .userId(user.getId())
                .username(user.getUsername())
                .message("登录成功")
                .build();
    }

    public User getUserById(Long userId) {
        return userRepository.findById(userId)
                .orElseThrow(() -> new RuntimeException("用户不存在"));
    }
}