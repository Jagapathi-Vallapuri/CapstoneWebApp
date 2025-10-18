#!/usr/bin/env node
// Detect the primary LAN IPv4 address and start Vite with VITE_API_BASE_URL set to that host.
import { execSync } from 'child_process';
import os from 'os';

function isPrivateIPv4(addr) {
  return (
    addr.startsWith('192.168.') ||
    addr.startsWith('10.') ||
    /^172\.(1[6-9]|2\d|3[0-1])\./.test(addr)
  );
}

function getLanIp() {
  const ifaces = os.networkInterfaces();
  // Prefer private IPv4s
  for (const name of Object.keys(ifaces)) {
    for (const iface of ifaces[name]) {
      if (iface.family === 'IPv4' && !iface.internal && isPrivateIPv4(iface.address)) {
        return iface.address;
      }
    }
  }
  // fallback to first non-internal IPv4
  for (const name of Object.keys(ifaces)) {
    for (const iface of ifaces[name]) {
      if (iface.family === 'IPv4' && !iface.internal) return iface.address;
    }
  }
  return 'localhost';
}

const host = getLanIp();
const apiPort = process.env.VITE_API_PORT || '8000';
const apiBase = `http://${host}:${apiPort}`;

console.log(`[dev-with-lan] Detected LAN IP: ${host}`);
console.log(`[dev-with-lan] Starting vite with VITE_API_BASE_URL=${apiBase}`);

// Support a dry-run flag so we can test detection without launching vite
if (process.argv.includes('--dry') || process.env.DRY_RUN === '1') {
  console.log('[dev-with-lan] Dry run - not starting vite.');
  console.log('[dev-with-lan] Export the following env vars to start vite manually:');
  console.log(`VITE_API_BASE_URL=${apiBase}`);
  console.log(`VITE_API_PORT=${apiPort}`);
  process.exit(0);
}

// Set env vars for the child process and start vite
process.env.VITE_API_BASE_URL = apiBase;
process.env.VITE_API_PORT = apiPort;

try {
  execSync('vite', { stdio: 'inherit', env: process.env });
} catch (err) {
  console.error('[dev-with-lan] Failed to start vite:', err.message || err);
  process.exit(1);
}
