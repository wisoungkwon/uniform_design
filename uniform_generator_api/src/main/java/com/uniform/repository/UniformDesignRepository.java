package com.uniform.repository;

import com.uniform.domain.UniformDesign;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;

public interface UniformDesignRepository extends JpaRepository<UniformDesign, Long> {
    
    /**
     * 특정 사용자가 만든 모든 유니폼 디자인 목록을 찾는 메서드
     * @param userId 사용자의 고유 ID
     * @return 해당 사용자가 만든 디자인 목록
     */
    List<UniformDesign> findByUserId(Long userId);
}