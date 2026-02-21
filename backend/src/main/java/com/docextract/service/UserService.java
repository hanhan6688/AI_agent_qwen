package com.docextract.service;

import com.docextract.dto.LoginRequest;
import com.docextract.dto.UserDTO;
import com.docextract.entity.User;
import com.docextract.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.HashMap;
import java.util.Map;
import java.util.Optional;

@Service
@RequiredArgsConstructor
public class UserService {

    private final UserRepository userRepository;

    public Map<String, Object> login(LoginRequest loginRequest) {
        Optional<User> userOpt = userRepository.findByUsername(loginRequest.getUsername());
        if (userOpt.isEmpty()) {
            throw new RuntimeException("用户名或密码错误");
        }

        User user = userOpt.get();
        if (!loginRequest.getPassword().equals(user.getPassword())) {
            throw new RuntimeException("用户名或密码错误");
        }

        Map<String, Object> result = new HashMap<>();
        result.put("user", convertToDTO(user));
        return result;
    }

    @Transactional
    public UserDTO register(String username, String password, String email) {
        if (userRepository.existsByUsername(username)) {
            throw new RuntimeException("用户名已存在");
        }
        if (userRepository.existsByEmail(email)) {
            throw new RuntimeException("邮箱已被使用");
        }

        User user = User.builder()
                .username(username)
                .password(password)
                .email(email)
                .documentCount(0)
                .build();

        user = userRepository.save(user);
        return convertToDTO(user);
    }

    public UserDTO getUserById(Long userId) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new RuntimeException("用户不存在"));
        return convertToDTO(user);
    }

    @Transactional
    public void incrementDocumentCount(Long userId) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new RuntimeException("用户不存在"));
        user.setDocumentCount(user.getDocumentCount() + 1);
        userRepository.save(user);
    }

    private UserDTO convertToDTO(User user) {
        return UserDTO.builder()
                .userId(user.getUserId())
                .username(user.getUsername())
                .email(user.getEmail())
                .documentCount(user.getDocumentCount())
                .createdAt(user.getCreatedAt())
                .updatedAt(user.getUpdatedAt())
                .build();
    }
}
