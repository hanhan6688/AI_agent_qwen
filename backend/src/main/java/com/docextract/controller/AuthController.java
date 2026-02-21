package com.docextract.controller;

import com.docextract.dto.LoginRequest;
import com.docextract.dto.Response;
import com.docextract.dto.UserDTO;
import com.docextract.service.UserService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
public class AuthController {

    private final UserService userService;

    @PostMapping("/login")
    public Response<Map<String, Object>> login(@Valid @RequestBody LoginRequest loginRequest) {
        Map<String, Object> result = userService.login(loginRequest);
        return Response.success("登录成功", result);
    }

    @PostMapping("/register")
    public Response<UserDTO> register(
            @RequestParam String username,
            @RequestParam String password,
            @RequestParam String email) {
        UserDTO user = userService.register(username, password, email);
        return Response.success("注册成功", user);
    }

    @GetMapping("/user/{userId}")
    public Response<UserDTO> getCurrentUser(@PathVariable Long userId) {
        UserDTO user = userService.getUserById(userId);
        return Response.success(user);
    }
}
