document.addEventListener('DOMContentLoaded', () => {
    const navMenu = document.getElementById('nav-menu');
    const generateButton = document.getElementById('generate-button');
    const keywordInput = document.getElementById('keyword-input');
    const uniformImage = document.getElementById('uniform-image');
    const imageCaption = document.getElementById('image-caption');
    const designForm = document.getElementById('design-form');

    // 이 변수는 나중에 백엔드로부터 로그인 상태를 받아올 것입니다.
    // 지금은 테스트를 위해 직접 설정합니다.
    let isLoggedIn = true;

    function updateNavMenu() {
        navMenu.innerHTML = ''; // 기존 메뉴 항목을 모두 제거

        let menuItems = [];
        if (isLoggedIn) {
            // 로그인 후 메뉴
            menuItems = [
                { text: '마이페이지', href: '#' },
                { text: '내 디자인 모아보기', href: '#' },
                { text: '디자인 공유 게시판', href: '#' }
            ];
        } else {
            // 로그인 전 메뉴
            menuItems = [
                { text: '로그인', href: '#' },
                { text: '회원가입', href: '#' },
                { text: '디자인 공유 게시판', href: '#' }
            ];
        }

        menuItems.forEach(item => {
            const li = document.createElement('li');
            const a = document.createElement('a');
            a.href = item.href;
            a.textContent = item.text;
            li.appendChild(a);
            navMenu.appendChild(li);
        });
    }

    // 페이지 로드 시 네비게이션 메뉴 업데이트
    updateNavMenu();

    // 이 함수를 사용하여 로그인 상태를 토글하고 메뉴를 업데이트할 수 있습니다.
    // 나중에 실제 로그인/로그아웃 버튼에 연결될 것입니다.
    window.toggleLoginStatus = () => {
        isLoggedIn = !isLoggedIn;
        updateNavMenu();
    };

    // 폼 제출 이벤트 리스너 (버튼 클릭 대신 폼 제출 이벤트 사용)
    designForm.addEventListener('submit', async (e) => {
        e.preventDefault(); // 폼 제출 시 페이지 새로고침 방지

        const keyword = keywordInput.value;
        const selectedStyle = document.querySelector('input[name="style"]:checked').value;

        if (keyword.trim() === '') {
            imageCaption.textContent = '키워드를 입력해주세요!';
            uniformImage.style.display = 'none';
            return;
        }

        imageCaption.textContent = '이미지 생성 중... 잠시만 기다려주세요.';
        uniformImage.style.display = 'none';

        try {
            // Flask API 호출 코드로 교체된 부분
            const response = await fetch('http://localhost:8000/generate-uniform', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ keyword: keyword, style: selectedStyle }),
            });

            const data = await response.json();

            if (response.ok) {
                // Flask 서버로부터 받은 이미지 URL을 사용합니다.
                uniformImage.src = data.imageUrl;
                uniformImage.onload = () => {
                    uniformImage.style.display = 'block';
                    imageCaption.textContent = '생성된 디자인이 여기 있습니다!';
                };
            } else {
                imageCaption.textContent = `오류: ${data.error}`;
                uniformImage.style.display = 'none';
            }
        } catch (error) {
            console.error('API 호출 중 오류 발생:', error);
            imageCaption.textContent = '이미지 생성에 실패했습니다. 다시 시도해주세요.';
            uniformImage.style.display = 'none';
        }
    });
});