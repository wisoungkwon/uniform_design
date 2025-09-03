document.addEventListener('DOMContentLoaded', () => {
	const navMenu = document.getElementById('nav-menu');
	const keywordInput = document.getElementById('keyword-input');
	const uniformImage = document.getElementById('uniform-image');
	const imageCaption = document.getElementById('image-caption');
	const designForm = document.getElementById('design-form');
	const advanced = document.getElementById('advanced-details');

	// 메뉴(기존 그대로)
	let isLoggedIn = false;
	function updateNavMenu() {
		navMenu.innerHTML = '';
		const items = isLoggedIn
			? [{ text: '마이페이지', href: '#' }, { text: '내 디자인 모아보기', href: '#' }, { text: '디자인 공유 게시판', href: '#' }]
			: [{ text: '로그인', href: '#' }, { text: '회원가입', href: '#' }, { text: '디자인 공유 게시판', href: '#' }];
		items.forEach(i => {
			const li = document.createElement('li');
			const a = document.createElement('a');
			a.href = i.href; a.textContent = i.text;
			li.appendChild(a); navMenu.appendChild(li);
		});
	}
	updateNavMenu();

	// 최소한의 유효성 + 기본값 결합
	function buildPayload(formEl) {
		const fd = new FormData(formEl);
		const get = (name, fallback = null) => (fd.get(name) ?? fallback);

		// 필수 5개
		const keyword = (get('keyword', '') || '').trim();
		const sport = get('sport', 'baseball');
		const uniformStyle = get('uniform_style', 'short_sleeve_tshirt');
		const playerName = (get('player_name', '') || '').trim();
		const playerNumber = get('player_number', '');

		// 기본값(백엔드에서 안 주면 이 값 사용)
		const defaults = {
			name_style: 'english',
			name_position: 'back',
			name_uppercase: 'on',
			number_size: 'medium',
			number_position: 'back'
		};

		// 고급 설정이 닫혀 있으면 최소 필드 + 기본값만 전송
		let advancedFields = {};
		if (advanced && advanced.open) {
			// 열려 있을 때만 실제 값 수집 (체크 안 한 건 기본값 유지)
			advancedFields = {
				name_style: get('name_style', defaults.name_style),
				name_position: get('name_position', defaults.name_position),
				name_uppercase: fd.has('name_uppercase') ? 'on' : undefined,
				name_shadow: fd.has('name_shadow') ? 'on' : undefined,
				number_size: get('number_size', defaults.number_size),
				number_position: get('number_position', defaults.number_position)
			};
			// undefined 제거
			Object.keys(advancedFields).forEach(k => advancedFields[k] === undefined && delete advancedFields[k]);
		}

		// Flask가 기대하는 키: keyword, style
		return {
			keyword,
			style: uniformStyle,
			sport,
			player_name: playerName,
			player_number: playerNumber,
			// 고급 설정 or 기본값
			...defaults,
			...advancedFields
		};
	}

	designForm.addEventListener('submit', async (e) => {
		e.preventDefault();

		const nameInput = document.getElementById('player_name');
		const numInput = document.getElementById('player_number');

		if (!keywordInput.value.trim()) {
			imageCaption.textContent = '키워드를 입력해주세요!';
			uniformImage.style.display = 'none';
			return;
		}
		if (!nameInput.checkValidity()) { nameInput.reportValidity(); return; }
		if (!numInput.checkValidity()) { numInput.reportValidity(); return; }

		const payload = buildPayload(designForm);

		imageCaption.textContent = '이미지 생성 중... 잠시만 기다려주세요.';
		uniformImage.style.display = 'none';

		try {
			const response = await fetch('http://localhost:8000/generate-uniform', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(payload),
			});
			const data = await response.json();

			if (response.ok && data.imageUrl) {
				uniformImage.src = data.imageUrl;
				uniformImage.onload = () => {
					uniformImage.style.display = 'block';
					imageCaption.textContent = data.caption || '생성된 디자인이 여기 있습니다!';
				};
			} else {
				imageCaption.textContent = `오류: ${data.error || '이미지 생성 실패'}`;
				uniformImage.style.display = 'none';
			}
		} catch (err) {
			console.error(err);
			imageCaption.textContent = '이미지 생성에 실패했습니다. 다시 시도해주세요.';
			uniformImage.style.display = 'none';
		}
	});
});
