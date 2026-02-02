package com.docextract.controller;

import com.docextract.dto.ApiResponse;
import com.docextract.dto.LoginRequest;
import com.docextract.dto.LoginResponse;
import com.docextract.service.AuthService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

@Slf4j
@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
@CrossOrigin(origins = "*")
public class AuthController {

    private final AuthService authService;

    @PostMapping("/login")
    public ApiResponse<LoginResponse> login(@Valid @RequestBody LoginRequest request) {
        try {
            LoginResponse response = authService.login(request);
            return ApiResponse.success("登录成功", response);
        } catch (Exception e) {
            log.error("登录失败", e);
            return ApiResponse.error(401, e.getMessage());
        }
    }

    @GetMapping("/user/{userId}")
    public ApiResponse<?> getUser(@PathVariable Long userId) {
        try {
            var user = authService.getUserById(userId);
            return ApiResponse.success(user);
        } catch (Exception e) {
            log.error("获取用户信息失败", e);
            return ApiResponse.error(404, e.getMessage());
        }
    }
}
