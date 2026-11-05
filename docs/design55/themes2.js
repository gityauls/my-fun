// 추가 색 테마 10종. 화면 구성은 그대로, 색 토큰만 다르다.
const artSvg = ([sky, sun, hill1, hill2]) => 'data:image/svg+xml,' + encodeURIComponent(
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" fill="${sky}"/><circle cx="45" cy="19" r="10" fill="${sun}"/><path d="M0 46 C12 34 22 34 32 42 C42 50 52 40 64 34 V64 H0 Z" fill="${hill1}"/><path d="M0 54 C14 46 26 50 38 54 C48 57 56 52 64 48 V64 H0 Z" fill="${hill2}"/></svg>`);

const cover = (art, acc, g2, bg, tabs, tint) => ({
  art, v: { bg, bar: tabs, barFg: '#F1F3F5', tabs, ink: '#F1F3F5', mute: '#B4BCC6', line: 'rgba(255,255,255,.12)', acc, accT: acc, g1: acc, g2, onAcc: '#14171C', track: 'rgba(255,255,255,.22)', tint, icon: '#E4E8EE', edge: 'rgba(255,255,255,.1)', shadow: '0 14px 34px rgba(12,12,24,.4)', ctrlBg: 'rgba(255,255,255,.1)', fav: acc, miniEdge: 'rgba(255,255,255,.2)', tabFg: '#B4BCC6' } });

module.exports = (ART) => {
  const c1 = cover(ART.light, '#C9B6FF', '#A48BEA', '#1E1A2E', '#17142A', '#352C52');
  const c2 = cover(ART.mid, '#7FD6CF', '#4DB5AD', '#12242A', '#0E1C21', '#1C3D42');
  const c3 = cover(ART.dark, '#9DB0FF', '#7388EE', '#141A36', '#10152C', '#26305E');
  const c4 = cover(artSvg(['#E9A98F', '#FFE3C2', '#B85C4E', '#5E2C33']), '#FFB4A2', '#F08E78', '#2A1A1C', '#211416', '#47292B');
  return [
    { id: 'c', n: 'C 앨범 색', d: '곡의 그림에서 색을 뽑아 곡마다 색이 바뀝니다', ...c1,
      variants: [['바다 그림 곡', c2], ['밤 도시 그림 곡', c3], ['노을 그림 곡', c4]] },
    { id: 'd', n: 'D 흑연', d: '짙은 회색 바탕 · 코랄 포인트', art: artSvg(['#3A3432', '#F08A72', '#5A5350', '#2A2726']),
      v: { bg: '#1C1A19', bar: '#151312', barFg: '#F2EFEC', tabs: '#242120', ink: '#F2EFEC', mute: '#ADA6A0', line: '#35312F', acc: '#F08A72', accT: '#F4A08B', g1: '#F59A82', g2: '#E0705A', onAcc: '#2A120C', track: '#4A4542', tint: '#332B28', icon: '#DDD8D3', edge: '#2C2826', shadow: '0 14px 34px rgba(0,0,0,.45)', ctrlBg: '#2E2A28', fav: '#F4A08B', miniEdge: '#4A4542' } },
    { id: 'f', n: 'F 서리', d: '푸른 회색 상단에 뽀얀 바탕', art: artSvg(['#C6CDD8', '#ECEDED', '#8D94A2', '#474C58']),
      v: { bg: '#ECEDED', bar: '#666D7D', barFg: '#FFFFFF', tabs: '#E4E5E4', ink: '#23262E', mute: '#474C58', line: '#D3D6DA', acc: '#4B5160', accT: '#3B404D', g1: '#666D7D', g2: '#474C58', onAcc: '#FFFFFF', track: '#BCC2CC', tint: '#D8DCE3', icon: '#2E323C', edge: '#D3D6DA', shadow: '0 14px 34px rgba(50,56,72,.2)', ctrlBg: '#DCDEE1', fav: '#3B404D', miniEdge: '#9AA2B1' } },
    { id: 'g', n: 'G 세이지', d: '차분한 녹회색', art: artSvg(['#C9D2C3', '#EEF1EA', '#7F8D7C', '#4E5A4C']),
      v: { bg: '#EEF1EA', bar: '#6A7867', barFg: '#FFFFFF', tabs: '#E6EBE1', ink: '#232B22', mute: '#4E5A4C', line: '#D5DCCF', acc: '#5C6A59', accT: '#47544A', g1: '#7F8D7C', g2: '#4E5A4C', onAcc: '#FFFFFF', track: '#C9D2C3', tint: '#DCE3D6', icon: '#2E382D', edge: '#D5DCCF', shadow: '0 14px 34px rgba(60,75,55,.2)', ctrlBg: '#E0E6DA', fav: '#47544A', miniEdge: '#A9B5A5' } },
    { id: 'h', n: 'H 남보라', d: '연보라 바탕에 남색 재생 영역', art: artSvg(['#B4B8D2', '#F2F3FA', '#54587A', '#23264A']),
      v: { bg: '#E7E9F6', bar: '#23264A', barFg: '#F2F3FA', tabs: '#D9DCEA', tabFg: '#3A3E63', ink: '#23264A', mute: '#54587A', line: '#C9CCE2', acc: '#3A3E63', accT: '#2C2F4D', g1: '#3A3E63', g2: '#23264A', onAcc: '#F2F3FA', track: '#C5C9E2', tint: '#D2D5EA', icon: '#2C2F4D', edge: '#D9DCEA', shadow: '0 14px 34px rgba(44,47,77,.25)', ctrlBg: '#D9DCEA', fav: '#3A3E63', miniEdge: '#8D92BB' },
      hero: { bg: '#2C2F4D', ink: '#F2F3FA', mute: '#C5C9E2', icon: '#F2F3FA', ic2: '#C9CCE2', track: '#54587A', acc: '#C9CCE2', acc2: '#C9CCE2', accT: '#C9CCE2', g1: '#F2F3FA', g2: '#C9CCE2', onAcc: '#23264A', line: '#54587A' } },
    { id: 'i', n: 'I 숲과 테라코타', d: '아이보리 · 숲색 · 민트 · 테라코타 · 남색', art: artSvg(['#E9D9BD', '#C8643C', '#3F7A63', '#1E3A52']),
      v: { bg: '#F4EEE3', bar: '#1F4D3A', barFg: '#FBF7EF', tabs: '#DCEBDD', tabFg: '#2E5A48', tabOn: '#A8481F', tabLine: '#C8643C', ink: '#22302A', mute: '#5C665F', line: '#DCD3C3', acc: '#C8643C', accT: '#A8481F', g1: '#D97A50', g2: '#C05A32', onAcc: '#FFFFFF', track: '#DCD3C3', tint: '#1F4D3A', rowFg: '#FBF7EF', icon: '#22302A', ic2: '#1E3A52', acc2: '#1F4D3A', edge: '#DCD3C3', shadow: '0 14px 34px rgba(50,60,40,.22)', ctrlBg: '#E8DFCF', fav: '#1E4F78', miniEdge: '#3F7A63', stripBg: '#FBF7EF' },
      foot: [['#1F4D3A', '#FFFFFF'], ['#B7D9C1', '#1F3D30'], ['#E8B98E', '#4A2A14'], ['#1E3A52', '#FFFFFF']],
      spec: ['#C8643C', '#3F7A63', '#1E3A52'],
      hero: { bg: '#1F4D3A', ink: '#FBF7EF', mute: '#B7D9C1', icon: '#FBF7EF', ic2: '#B7D9C1', track: '#3C6F5B', acc: '#E8926B', acc2: '#B7D9C1', accT: '#E8926B', line: '#3C6F5B', g1: '#E8926B', g2: '#C8643C' } },
    { id: 'j', n: 'J 파스텔 타일', d: '크림 · 살구 · 민트 · 레몬 · 하늘색 타일', art: artSvg(['#B5CBE3', '#F5D482', '#EF8C6D', '#A8CDBE']),
      v: { bg: '#FFF8EE', bar: '#EF8C6D', barFg: '#3A1A10', tabs: '#F5D482', tabFg: '#3B3A36', tabOn: '#1F3A33', tabLine: '#3B3A36', ink: '#3B3A36', mute: '#6B675E', line: '#ECDCC6', acc: '#E0704F', accT: '#B53B28', g1: '#F2A088', g2: '#E0704F', onAcc: '#3A1A10', track: '#ECDCC6', tint: '#A8CDBE', rowFg: '#1F3A33', icon: '#3B3A36', ic2: '#2A6197', acc2: '#2F8F7A', edge: '#ECDCC6', shadow: '0 14px 34px rgba(150,100,60,.2)', ctrlBg: '#F5E7D2', fav: '#2A6197', miniEdge: '#EF8C6D', stripBg: '#FBEEDD' },
      tabBg: ['#F6B7A1', '#A8CDBE', '#F5D482', '#B5CBE3'],
      foot: [['#A8CDBE', '#1F3A33'], ['#F6B7A1', '#4A2013'], ['#F5D482', '#4A3A0C'], ['#B5CBE3', '#1D3550']],
      spec: ['#EF8C6D', '#F2B93F', '#5FAE97', '#7FA6D1'],
      mini: { bg: 'linear-gradient(90deg,#F6B7A1 0 104px,#A8CDBE 104px 329px,#F5D482 329px 519px,#B5CBE3 519px)', line: 'transparent', mute: '#3B3A36', track: '#FFF8EE', acc: '#3B3A36', acc2: '#3B3A36', accT: '#3B3A36', ic2: '#3B3A36', g1: '#3B3A36', g2: '#2A2926', onAcc: '#FFF8EE' } },
    { id: 'k', n: 'K 흙과 올리브', d: '모래색 · 올리브 · 갈색 · 황토색', art: artSvg(['#D9B98A', '#F0DCB0', '#8A5A3C', '#5E6B43']),
      v: { bg: '#F6EFE2', bar: '#5E6B43', barFg: '#F6EFE2', tabs: '#E6DAC6', tabFg: '#3A2F25', tabOn: '#6B3F22', tabLine: '#8A5A3C', ink: '#3A2F25', mute: '#695B4C', line: '#D6C9B3', acc: '#5E6B43', accT: '#5E6B43', g1: '#9A6A4A', g2: '#8A5A3C', onAcc: '#FFFFFF', track: '#D6C9B3', tint: '#5E6B43', rowFg: '#F6EFE2', icon: '#3A2F25', ic2: '#8A5A3C', acc2: '#8A5A3C', edge: '#D6C9B3', shadow: '0 14px 34px rgba(90,66,38,.22)', ctrlBg: '#E6DAC6', fav: '#8A5A3C', miniEdge: '#C9A67A' },
      foot: [['#5E6B43', '#FFFFFF'], ['#8A5A3C', '#FFFFFF'], ['#C9A67A', '#3A2613'], ['#E6DAC6', '#3A2F25']],
      spec: ['#5E6B43', '#8A5A3C', '#C98F3F'] },
    { id: 'l', n: 'L 노을', d: '노을 그라데이션 · 남색 · 금색', art: artSvg(['#F6C88E', '#FFF1D6', '#C0647A', '#2B3D63']),
      v: { bg: '#FBF8F4', bar: 'linear-gradient(90deg,#2B3D63,#8A5A7C 55%,#C46A5A)', barFg: '#FFFFFF', tabs: '#F3DCC5', tabFg: '#3F2412', tabOn: '#1E2F4D', tabLine: '#1E2F4D', ink: '#22304A', mute: '#566377', line: '#E3DDD5', acc: '#C98638', accT: '#8F5716', g1: '#F0B080', g2: '#E9906A', onAcc: '#3F2412', track: '#E3DDD5', tint: '#F6C8A2', rowFg: '#3F2412', icon: '#22304A', ic2: '#1F5EA8', acc2: '#C98638', edge: '#E3DDD5', shadow: '0 14px 34px rgba(70,60,110,.28)', ctrlBg: '#EFE6DC', fav: '#B23320', miniEdge: '#C98638' },
      foot: [['#1E2F4D', '#FFFFFF'], ['#E9A06C', '#3F2412'], ['#F3D9A4', '#4A3410'], ['#9FC0D8', '#14304A']],
      spec: ['#2B3D63', '#8A5A7C', '#E9906A', '#E2A95C'],
      hero: { bg: 'linear-gradient(170deg,#2B3D63 0%,#6F4F7E 48%,#B05F62 82%,#C46A5A 100%)', ink: '#FFFFFF', mute: '#FFE9D4', icon: '#FFFFFF', ic2: '#FFE08F', track: 'rgba(255,255,255,.35)', acc: '#FFE08F', acc2: '#FFE08F', accT: '#FFE08F', line: 'rgba(255,255,255,.3)' },
      mini: { bg: 'linear-gradient(100deg,#2B3D63 0%,#6F4F7E 45%,#B05F62 80%,#C46A5A 100%)', ink: '#FFFFFF', mute: '#FFE9D4', icon: '#FFFFFF', ic2: '#FFE08F', track: 'rgba(255,255,255,.35)', acc: '#FFE08F', acc2: '#FFE08F', accT: '#FFE08F', line: 'rgba(255,255,255,.3)' } },
    { id: 'm', n: 'M 청록과 구리', d: '청록 회색 · 크림 · 구리색 · 복숭아', art: artSvg(['#A9C4BD', '#F2D9BC', '#D18F54', '#3E6B68']),
      v: { bg: '#F5F0E6', bar: '#3E6B68', barFg: '#FFFFFF', tabs: '#A9C4BD', tabFg: '#27393A', tabOn: '#1F4744', tabLine: '#1F4744', ink: '#27393A', mute: '#546A69', line: '#D9D3C5', acc: '#C07A3E', accT: '#8F5219', g1: '#D18F54', g2: '#B97638', onAcc: '#2E1A08', track: '#D9D3C5', tint: '#F2D9BC', rowFg: '#4A2C10', icon: '#27393A', ic2: '#3E6B68', acc2: '#3E6B68', edge: '#D9D3C5', shadow: '0 14px 34px rgba(40,70,70,.26)', ctrlBg: '#E7E0D2', fav: '#8F5219', miniEdge: '#3E6B68', stripBg: '#EFE7D8' },
      foot: [['#3E6B68', '#FFFFFF'], ['#D18F54', '#2E1A08'], ['#F2D9BC', '#4A2C10'], ['#A9C4BD', '#27393A']],
      spec: ['#3E6B68', '#D18F54', '#7FA89F'],
      mini: { bg: '#A9C4BD', mute: '#2F4443', line: '#7FA19A', track: '#7FA19A', acc: '#27393A', acc2: '#27393A', accT: '#27393A', ic2: '#27393A' } },
  ];
};
