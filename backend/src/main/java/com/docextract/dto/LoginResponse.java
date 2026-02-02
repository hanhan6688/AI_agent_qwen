package com.docextract.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class LoginResponse {

    private Long userId;
    private String username;
    private String token; // 预留，当前版本不使用JWT
    private String message;
}
