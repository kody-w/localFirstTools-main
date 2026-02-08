const fs = require('fs');
const path = require('path');
const base = '/Users/kodyw/Projects/localFirstTools-main';

// 1. Create directory
const dir = path.join(base, 'apps/archive/evomon-world-generator');
fs.mkdirSync(dir, { recursive: true });
console.log('Created:', dir);

// 2. Move file
const src = path.join(base, 'apps/archive/evomon-world-generator-v1.html');
const dst = path.join(dir, 'v1.html');
fs.renameSync(src, dst);
console.log('Moved:', src, '->', dst);

// 3. Verify
const files = fs.readdirSync(dir);
files.forEach(f => {
  const s = fs.statSync(path.join(dir, f));
  console.log('  ', f, s.size, 'bytes');
});

// 4. Clean up _tmp_mkdir.sh
const tmp = path.join(base, '_tmp_mkdir.sh');
if (fs.existsSync(tmp)) { fs.unlinkSync(tmp); console.log('Removed _tmp_mkdir.sh'); }
else { console.log('_tmp_mkdir.sh not found (already clean)'); }

// 5. Clean up this script
fs.unlinkSync(path.join(base, '_do_archive_ops.js'));
console.log('Self-cleaned _do_archive_ops.js');
console.log('ALL DONE');
