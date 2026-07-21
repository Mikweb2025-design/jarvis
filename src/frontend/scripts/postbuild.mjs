import fs from 'fs';
import path from 'path';

const root = path.resolve(process.cwd(), '../..');
const dist = path.join(root, 'dist/frontend');
const dst = path.join(root, 'assets');

// Copy built JS to assets/
const srcDir = path.join(dist, 'assets');
if (fs.existsSync(srcDir)) {
  fs.readdirSync(srcDir)
    .filter(f => f.endsWith('.js'))
    .forEach(f => {
      fs.copyFileSync(path.join(srcDir, f), path.join(dst, f));
      console.log('  assets/' + f);
    });
}

// Inject avatar3d.js into built index.html
const htmlPath = path.join(dist, 'index.html');
if (fs.existsSync(htmlPath)) {
  let html = fs.readFileSync(htmlPath, 'utf8');
  html = html.replace(
    '<script src="/assets/app.js"></script>',
    '<script src="/assets/app.js"></script>\n<script type="module" src="/assets/avatar3d.js"></script>'
  );
  fs.writeFileSync(htmlPath, html);
  console.log('  injected avatar3d.js into index.html');
}
