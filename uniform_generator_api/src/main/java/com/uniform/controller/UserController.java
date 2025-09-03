package com.uniform.controller;

import com.uniform.domain.User;
import com.uniform.repository.UserRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/users")
public class UserController {

    @Autowired
    private UserRepository userRepository;

    @PostMapping("/signup")
    public ResponseEntity<String> signUp(@RequestBody User user) {
        try {
            // 사용자 이름 중복 확인
            if (userRepository.findByUsername(user.getUsername()) != null) {
                return new ResponseEntity<>("이미 존재하는 사용자 이름입니다.", HttpStatus.CONFLICT);
            }
            
            // 비밀번호 암호화 (나중에 추가)
            // String encodedPassword = passwordEncoder.encode(user.getPassword());
            // user.setPassword(encodedPassword);

            userRepository.save(user);
            return new ResponseEntity<>("회원가입이 성공적으로 완료되었습니다.", HttpStatus.CREATED);
        } catch (Exception e) {
            return new ResponseEntity<>("회원가입에 실패했습니다.", HttpStatus.INTERNAL_SERVER_ERROR);
        }
    }

    @PostMapping("/login")
    public ResponseEntity<String> login(@RequestBody User user) {
        User foundUser = userRepository.findByUsername(user.getUsername());
        if (foundUser == null || !foundUser.getPassword().equals(user.getPassword())) {
            return new ResponseEntity<>("사용자 이름 또는 비밀번호가 올바르지 않습니다.", HttpStatus.UNAUTHORIZED);
        }
        
        // 로그인 성공 시 세션 또는 JWT 토큰 발급 (나중에 추가)
        return new ResponseEntity<>("로그인에 성공했습니다.", HttpStatus.OK);
    }
}