// Editable vector artwork for category, animal, boss and bean soul icons.
// Run with Node.js and sharp available. Generated PNGs are checked in, so normal
// builds do not need Node or sharp. Native textures stay 32x32 RGBA32; GUI uses 128.
const fs = require('fs');
const path = require('path');
const sharp = require('sharp');
const root = path.resolve(__dirname, '..');
const target = path.join(root, 'soh/assets/custom/textures/parameter_static');
const vectorDir = path.join(root, 'tools/soul-emblems');
fs.mkdirSync(vectorDir, {recursive:true});
const p = (d, fill='url(#ivory)', extra='') => `<path d="${d}" fill="${fill}" ${extra}/>`;
const line = d => p(d, 'none', 'stroke="#203543" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"');
const eye = (x,y,r=3) => `<circle cx="${x}" cy="${y}" r="${r}" fill="#162636"/>`;
const leaf = p('M62 94V58 M61 76Q27 77 30 48Q61 44 62 76 M64 63Q66 31 98 34Q98 64 64 63', 'url(#ivory)') + line('M62 92V63 M39 57L59 73 M73 55L88 43');
const flame = p('M65 29Q87 53 80 60L88 49Q106 89 72 100Q30 109 34 72Q39 80 46 81Q36 54 65 29Z') + p('M65 62Q59 78 54 84Q53 96 65 98Q83 94 72 79L70 89Z','#223b48');
const glyphs = {
 ENEMY: p('M36 51Q35 29 64 28Q93 29 92 54L86 76L78 78V94H50V78L41 76Z') + eye(51,57,7)+eye(77,57,7)+p('M64 66L59 77H69Z','#203543')+line('M58 84V93 M70 84V93'),
 NPC: p('M45 50Q44 28 65 28Q85 29 83 51Q79 69 64 69Q49 69 45 50 M29 98Q30 77 49 75L64 85L79 75Q98 78 99 98Z')+p('M77 57L91 48L89 67L78 70Z')+line('M47 40Q60 49 78 38'),
 ANIMAL: p('M43 78Q52 64 63 64Q74 64 87 82Q97 101 78 102L64 97L48 103Q28 102 34 88Z') + '<ellipse cx="35" cy="60" rx="10" ry="14" fill="url(#ivory)" transform="rotate(-25 35 60)"/><ellipse cx="54" cy="44" rx="10" ry="14" fill="url(#ivory)"/><ellipse cx="78" cy="45" rx="10" ry="14" fill="url(#ivory)"/><ellipse cx="95" cy="63" rx="9" ry="13" fill="url(#ivory)" transform="rotate(25 95 63)"/>',
 POT: p('M46 31H82V41H77Q74 52 86 63Q101 95 77 101H50Q26 94 41 65Q53 52 50 41H46Z')+line('M46 41H81 M38 74H91 M38 84H91')+p('M48 55Q41 67 45 89L51 93Q47 67 56 53Z','#fff4d3','opacity=".5"'),
 CRATE: p('M31 39L79 29L98 43V90L49 103L31 88Z')+p('M49 55L98 43V90L49 103Z','#cba56d')+line('M31 39L49 55V103 M49 55L98 43 M35 47L44 85 M37 88L45 61 M55 63L91 86 M90 55L56 93'),
 GRASS: p('M30 100Q41 84 28 54Q52 66 54 85Q48 47 60 29Q65 64 70 80Q76 53 94 42Q88 65 85 88Q97 75 105 76L94 99Z')+line('M53 96L43 73 M68 95L62 58 M81 96L86 65'),
 ROCK: p('M27 83L39 47L76 32L99 61L102 89L68 103L39 97Z')+p('M39 47L62 61L76 32Z','#edf4ee')+p('M62 61L99 61L102 89L68 103Z','#93aab1')+line('M39 47L62 61L68 103 M62 61L99 61 M62 61L76 32'),
 TREE: p('M55 100L58 77H42Q21 68 34 49Q30 33 52 34Q69 18 81 35Q103 32 100 51Q114 74 86 81H71L75 100Z')+line('M64 97V60 M64 78L49 65 M64 70L80 53'),
 BEEHIVE: p('M57 26H70L73 39Q87 42 87 50Q100 60 93 68Q108 81 97 89Q94 103 65 105Q33 103 31 88Q21 78 36 66Q29 57 42 49Q43 40 56 39Z')+line('M41 53H87 M35 68H93 M32 83H98 M39 96H90')+'<ellipse cx="65" cy="81" rx="10" ry="12" fill="#203543"/>',
 SIGN: p('M29 37H92L103 52L92 68H72V103H59V68H29Z')+line('M39 47H82 M39 58H72')+eye(88,52,2),
 COW: p('M47 42Q30 45 29 26Q45 29 50 35L78 35Q85 28 98 27Q98 45 81 45L80 79H47Z')+p('M47 49L29 43L35 61L48 64 M80 50L99 43L94 61L80 64')+p('M49 35L61 37L60 60L47 57Z','#354653')+p('M43 79Q64 68 85 79L86 94Q64 107 42 93Z','#e4ae94')+eye(54,88)+eye(75,88)+eye(72,54)+eye(52,55),
 CUCCO: p('M37 67Q25 54 28 43L45 53Q45 37 58 35L81 40L88 58Q103 84 83 98H49Q29 91 37 67Z')+p('M58 36Q48 24 58 24Q66 21 70 32Q78 24 83 30L81 42Z','#ed786e')+p('M80 48L101 55L83 61Z','#eac16d')+eye(75,47)+line('M49 65Q40 84 68 86 M57 99L51 106 M75 99L81 106'),
 DOG: p('M42 40L31 56L35 79L47 73L51 93Q67 102 80 90L85 69L97 76L98 51L82 37Z')+p('M43 39L46 67L35 79L30 55Z','#a7795a')+p('M82 38L82 68L96 76L99 51Z','#a7795a')+eye(55,60)+eye(74,60)+p('M61 72H72L67 80Z','#203543')+line('M67 80V88L58 86 M67 88L75 85'),
 FISH: p('M25 67Q53 23 85 52L105 38L101 69L106 92L84 80Q57 106 25 67Z')+p('M50 43L65 29L74 47 M51 88L65 102L75 86')+eye(43,61,4)+line('M60 49Q48 66 59 85 M66 63L79 69L65 77'),
 BUG: p('M50 45Q46 27 64 27Q82 27 78 45Q99 66 83 92Q64 108 45 92Q29 65 50 45Z')+line('M64 46V98 M45 55L31 47 M42 69L25 70 M46 86L32 96 M83 55L97 47 M86 69L103 70 M82 86L97 96 M55 32L47 22 M73 32L81 22'),
 BUTTERFLY: p('M62 60Q35 24 25 36Q18 64 48 71Q22 79 38 99Q51 106 62 80H66Q77 106 90 99Q106 79 80 71Q110 64 103 36Q93 24 66 60Z')+line('M64 49V86 M61 53L53 37 M67 53L76 37 M35 46L53 63 M93 46L75 63')+p('M40 85L53 79L48 91Z','#203543')+p('M88 85L75 79L80 91Z','#203543'),
 FROG: p('M38 45Q30 25 48 25Q65 25 59 42H72Q67 25 84 25Q102 25 93 47Q108 62 94 78L103 99L79 95L66 83L50 97L25 101L36 77Q19 60 38 45Z')+eye(47,36,5)+eye(83,36,5)+line('M40 60Q64 81 89 60 M38 83L50 82 M81 81L92 84'),
 HORSE: p('M38 98Q48 82 46 66L31 65L27 53L53 35L55 22L66 32L76 27Q99 43 98 77L92 102H76L77 62L60 58L56 99Z')+p('M70 33Q99 42 98 83L86 77Q88 49 68 45Z','#614735')+eye(55,47)+line('M29 54L43 58 M79 62L79 89'),
 GOHMA: p('M23 65Q64 17 106 65Q64 105 23 65Z')+ '<ellipse cx="64" cy="65" rx="17" ry="26" fill="#da854b"/>'+p('M64 41L70 65L64 88L58 65Z','#18262c')+line('M35 45L27 34 M64 31V20 M93 45L103 33'),
 KING_DODONGO: p('M29 48L40 26L51 43L77 42L91 26L98 52L89 84L77 99H49L30 82Z')+p('M44 68H84L90 85H35Z','#bc8a6c')+eye(44,55,5)+eye(83,55,5)+line('M48 82H79')+p('M45 82L50 91L56 82 M70 82L77 91L81 82','#fff5d6'),
 BARINADE: p('M33 66Q29 25 63 25Q101 25 95 66Z')+line('M44 67Q25 84 43 103 M58 69Q76 89 56 107 M78 68Q67 89 88 102')+p('M54 39H68L61 53H78L55 75L60 57H48Z','#203543'),
 PHANTOM_GANON: p('M42 47L29 27L55 37L74 37L99 27L88 53L83 82L64 103L43 82Z')+eye(51,58,6)+eye(78,58,6)+p('M64 66L58 77H71Z','#203543')+line('M52 84L64 91L77 83'),
 VOLVAGIA: flame + p('M54 64L46 45L63 52L77 42L72 65L84 74L77 88L58 87L47 76Z','#eacbb1')+eye(60,71)+eye(74,70),
 MORPHA: p('M62 22Q53 46 35 63Q16 96 58 106Q105 111 101 78Q100 57 79 40L82 60Q68 51 62 22Z')+'<circle cx="62" cy="79" r="15" fill="#a168a3"/>'+line('M43 88Q60 104 82 87'),
 BONGO_BONGO: p('M35 86L28 68Q25 57 32 56L47 66L44 36Q44 26 51 28L57 53L58 23Q64 17 68 25L69 52L74 28Q82 24 84 33L79 58L88 45Q96 44 96 53L87 79L78 100H49Z')+p('M48 77Q64 59 81 77Q64 95 48 77Z','#203543')+eye(64,77,5),
 TWINROVA: '<g transform="translate(-10 8) scale(.78)">'+flame+'</g>'+'<g transform="translate(49 18) scale(.63)">'+p('M24 22L92 91 M92 22L24 91 M58 7V109 M9 57H108','none','stroke="url(#ivory)" stroke-width="11" stroke-linecap="round"')+'</g>',
 GANON: p('M41 47Q20 38 25 22L47 37H81L104 22Q109 40 87 49L89 78L77 99H49L36 79Z')+p('M48 70H80L88 87L77 96H50L40 84Z','#a3a97e')+eye(49,55,5)+eye(80,55,5)+p('M38 73L39 91L52 89 M89 73L89 91L77 89')+eye(56,81)+eye(73,81),
 BEAN: leaf,
};
const source = fs.readFileSync(path.join(root,'soh/Enhancements/randomizer/EnemySoulIcons.h'),'utf8');
const mappings = [...source.matchAll(/\{ (RG_\w+), \w+, (SOH_SOUL_\w+), (\d+), (\d+), (\d+) \}/g)];
const tokens=[];
async function main(){
 for(const [,item,kind,...rgb] of mappings) {
  if(kind==='SOH_SOUL_PORTRAIT') continue;
  const key=item.includes('_BEAN_SOUL')?'BEAN':item.replace('RG_ANIMAL_SOUL_', '').replace(/^RG_/, '').replace(/_SOUL$/, '');
  const glyph=glyphs[key]; if(!glyph) throw Error(item+' missing glyph '+key);
  const name=item.slice(3), color=`rgb(${rgb.join(',')})`;
  // A restrained enamel medallion: bright silhouette, dark inner field, fine
  // rim. Three large tonal regions remain readable at the native 32px size.
  const svg=`<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128"><defs><linearGradient id="ivory" x2=".3" y2="1"><stop stop-color="#fff4d3"/><stop offset=".55" stop-color="#e5d8ac"/><stop offset="1" stop-color="#a99a71"/></linearGradient><linearGradient id="field" x2=".4" y2="1"><stop stop-color="#203e50"/><stop offset="1" stop-color="#0b172a"/></linearGradient><linearGradient id="rim" x2=".4" y2="1"><stop stop-color="#efffef"/><stop offset=".3" stop-color="${color}"/><stop offset="1" stop-color="#304e68"/></linearGradient></defs><path d="M64 5L104 22L122 64L104 106L64 123L24 106L6 64L24 22Z" fill="url(#rim)" stroke="#07101c" stroke-width="3"/><path d="M64 12L99 28L115 64L99 101L64 116L29 101L13 64L29 28Z" fill="url(#field)" stroke="${color}" stroke-width="1.5"/><g transform="translate(13 12) scale(.8)" stroke="#081a28" stroke-width="2.6" stroke-linejoin="round">${glyph}</g><path d="M60 112L64 106L68 112L64 118Z" fill="${color}"/></svg>`;
  fs.writeFileSync(path.join(vectorDir,name+'.svg'),svg+'\n');
  const stem='gSoulEmblem_'+name;
  for(const size of [32,128]) await sharp(Buffer.from(svg)).resize(size,size).png().toFile(path.join(target,stem+(size===128?'_GUI':'')+'.rgba32.png'));
  const raster=await sharp(Buffer.from(svg)).resize(64,64).png().toBuffer();
  for(let t=0;t<4;t++) await sharp(raster).extract({left:(t%2)*32,top:Math.floor(t/2)*32,width:32,height:32}).png().toFile(path.join(target,stem+'_Tile'+t+'.rgba32.png'));
  tokens.push({item,stem});
 }
 const decl=[],rows=[];
 for(const {item,stem} of tokens){
  for(const suf of ['', '_GUI','_Tile0','_Tile1','_Tile2','_Tile3']) decl.push(`static const ALIGN_ASSET(2) char ${stem+suf}[] = "__OTR__textures/parameter_static/${stem+suf}";`);
  rows.push(`    { ${item}, ${stem}, ${stem}_GUI, { ${stem}_Tile0, ${stem}_Tile1, ${stem}_Tile2, ${stem}_Tile3 } },`);
 }
 fs.writeFileSync(path.join(root,'soh/Enhancements/randomizer/SoulEmblemAssets.h'),`// Generated by tools/generate_soul_emblems.cjs. Native uploads are 32x32 RGBA32.\n#pragma once\n#include "align_asset_macro.h"\n#include "randomizerEnums.h"\nstruct SohSoulEmblem { RandomizerGet item; const char* icon; const char* gui; const char* tiles[4]; };\n${decl.join('\n')}\nstatic const SohSoulEmblem sSoulEmblems[] = {\n${rows.join('\n')}\n};\nstatic inline const SohSoulEmblem* SohExtreme_GetSoulEmblem(int item) {\n    for (const auto& emblem : sSoulEmblems) if (emblem.item == item) return &emblem;\n    return nullptr;\n}\n`);
 // A real bevel and sidewall, instead of the former portrait-only pickup.
 const bands=[[32,-4,95],[32,2,235],[35,4,255],[39,0,160],[36,-5,75]];
 const vertices=[];
 const vertex=(band,step)=>{const [r,z,shade]=bands[band],a=step*Math.PI/8;
  const light=Math.round(shade*(.8+.2*Math.cos(a-2.3)));
  return `    { { { ${Math.round(r*Math.cos(a))}, ${Math.round(r*Math.sin(a))}, ${z} }, 0, { 0, 0 }, { ${light}, ${light}, ${light}, 255 } } },`;};
 for(let band=0;band<bands.length-1;band++) for(let s=0;s<16;s++)
  for(const [b,i] of [[band,s],[band+1,s],[band+1,s+1],[band,s],[band+1,s+1],[band,s+1]]) vertices.push(vertex(b,i));
 fs.writeFileSync(path.join(root,'soh/Enhancements/randomizer/SoulRelicMesh.inc'),`// Generated by tools/generate_soul_emblems.cjs. Untextured beveled soul setting.\nstatic Vtx sSoulRelicRim[] = {\n${vertices.join('\n')}\n};\n`);
 console.log(`Generated ${tokens.length} editable soul emblems, 32px native icons, 128px GUI icons and safe 32px model tiles.`);
}
main().catch(e=>{console.error(e);process.exit(1)});
