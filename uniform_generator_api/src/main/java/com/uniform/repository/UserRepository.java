package com.uniform.repository;

import com.uniform.domain.User;
import org.springframework.data.jpa.repository.JpaRepository;

public interface UserRepository extends JpaRepository<User, Long> {
    // 사용자 이름으로 사용자 정보를 찾는 메서드 (로그인 기능에 사용)
    User findByUsername(String username);
}
