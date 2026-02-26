#!/usr/bin/env node
/* eslint-disable @typescript-eslint/no-require-imports */
/**
 * Enforce Zero "twin" in UI Copy - Phase 3 Testing
 * 
 * This script fails CI if any user-facing UI contains the word "twin"
 * Internal identifiers like twin_id are allowed.
 */

const fs = require('fs');
const path = require('path');

// ============================================================================
// Configuration
// ============================================================================

const TARGET_DIRS = [
  'frontend/app',
  'frontend/components',
  'frontend/lib'
];

const FILE_EXTENSIONS = ['.tsx', '.ts', '.jsx', '.js'];

// Patterns that are ALLOWED (internal identifiers, API paths, etc.)
const ALLOWED_PATTERNS = [
  /twin_id/,           // twin_id parameter
  /twinId/,            // camelCase twinId
  /\/twins\//,         // API path /twins/
  /\/twin\//,          // API path /twin/
  /\.twin\b/,          // object property .twin
  /twin\?\./,          // optional chaining twin?.
  /twin\./,            // object access twin.
  /['"]twin['"]/,      // string literal "twin" (often API endpoints)
  /\/\/.*twin/,        // comments
  /\/\*.*twin.*\*\//s, // block comments
];

// Patterns that indicate user-facing content (more strict checking)
const USER_FACING_PATTERNS = [
  /\bTwin\b/,           // Capitalized Twin
  /\btwin\b/,           // lowercase twin
  /\bTWIN\b/,           // uppercase TWIN
];

// ============================================================================
// Utility Functions
// ============================================================================

function shouldCheckFile(filePath) {
  const ext = path.extname(filePath);
  return FILE_EXTENSIONS.includes(ext) && !filePath.includes('node_modules');
}

function isAllowedLine(line) {
  // Check if line matches any allowed pattern
  return ALLOWED_PATTERNS.some(pattern => pattern.test(line));
}

function findTwinOccurrences(content, filePath) {
  const violations = [];
  const lines = content.split('\n');
  
  lines.forEach((line, index) => {
    // Skip if line is allowed
    if (isAllowedLine(line)) {
      return;
    }
    
    // Check for user-facing twin patterns
    USER_FACING_PATTERNS.forEach(pattern => {
      if (pattern.test(line)) {
        // Additional check: is this inside a string that's user-facing?
        // Look for JSX text content, label values, title attributes, etc.
        const isUserFacing = 
          />([^<]*twin[^<]*)</i.test(line) ||           // JSX text content
          /label\s*=\s*["'][^"']*twin/i.test(line) ||  // label prop
          /title\s*=\s*["'][^"']*twin/i.test(line) ||  // title prop
          /description\s*=\s*["'][^"']*twin/i.test(line) || // description prop
          /placeholder\s*=\s*["'][^"']*twin/i.test(line) || // placeholder
          /alt\s*=\s*["'][^"']*twin/i.test(line) ||    // alt text
          /h[1-6][^>]*>[^<]*twin/i.test(line) ||       // heading tags
          /<p[^>]*>[^<]*twin/i.test(line) ||           // paragraph tags
          /<span[^>]*>[^<]*twin/i.test(line) ||        // span tags
          /<div[^>]*>[^<]*twin/i.test(line) ||         // div text
          /toast\([^)]*twin/i.test(line) ||            // toast messages
          /showToast\([^)]*twin/i.test(line) ||        // showToast calls
          /alert\([^)]*twin/i.test(line);              // alert messages
        
        if (isUserFacing) {
          violations.push({
            line: index + 1,
            content: line.trim()
          });
        }
      }
    });
  });
  
  return violations;
}

function walkDir(dir, callback) {
  if (!fs.existsSync(dir)) {
    return;
  }
  
  const files = fs.readdirSync(dir);
  files.forEach(file => {
    const filePath = path.join(dir, file);
    const stat = fs.statSync(filePath);
    
    if (stat.isDirectory() && !file.includes('node_modules')) {
      walkDir(filePath, callback);
    } else if (stat.isFile()) {
      callback(filePath);
    }
  });
}

// ============================================================================
// Main
// ============================================================================

console.log('🔍 Checking for "twin" in user-facing UI copy...\n');

const allViolations = {};
let totalViolations = 0;

TARGET_DIRS.forEach(dir => {
  if (!fs.existsSync(dir)) {
    console.log(`⚠️  Directory not found: ${dir}`);
    return;
  }
  
  console.log(`📁 Checking ${dir}...`);
  const dirViolations = [];
  
  walkDir(dir, filePath => {
    if (!shouldCheckFile(filePath)) {
      return;
    }
    
    try {
      const content = fs.readFileSync(filePath, 'utf-8');
      const violations = findTwinOccurrences(content, filePath);
      
      if (violations.length > 0) {
        dirViolations.push({
          file: filePath,
          violations: violations
        });
      }
    } catch (err) {
      console.error(`  Error reading ${filePath}: ${err.message}`);
    }
  });
  
  if (dirViolations.length > 0) {
    allViolations[dir] = dirViolations;
    totalViolations += dirViolations.reduce((sum, v) => sum + v.violations.length, 0);
    console.log(`  ❌ Found ${dirViolations.length} file(s) with violations`);
  } else {
    console.log(`  ✅ No violations found`);
  }
});

// Special check for navigation config
console.log('\n📁 Checking navigation config...');
const navConfigPath = 'frontend/lib/navigation/config.ts';
if (fs.existsSync(navConfigPath)) {
  const content = fs.readFileSync(navConfigPath, 'utf-8');
  if (/APP_TAGLINE.*=.*['"][^'"]*[Tt]win[^'"]*['"]/.test(content)) {
    console.log('  ❌ APP_TAGLINE contains "twin"');
    totalViolations++;
  } else {
    console.log('  ✅ APP_TAGLINE is clean');
  }
} else {
  console.log('  ⚠️  Navigation config not found');
}

// ============================================================================
// Report
// ============================================================================

console.log('\n========================================');
console.log('SUMMARY');
console.log('========================================');

if (totalViolations > 0) {
  console.log(`\n❌ FAILED: Found ${totalViolations} violation(s)\n`);
  
  Object.entries(allViolations).forEach(([dir, files]) => {
    console.log(`\n📂 ${dir}:`);
    files.forEach(({ file, violations }) => {
      console.log(`  📄 ${file}:`);
      violations.forEach(v => {
        console.log(`    Line ${v.line}: ${v.content.substring(0, 80)}...`);
      });
    });
  });
  
  console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('The word "twin" must not appear in user-facing UI copy.');
  console.log('Internal identifiers like "twin_id", "twinId", "/twins/" are allowed.');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');
  process.exit(1);
} else {
  console.log('✅ PASSED: No "twin" violations found in UI copy');
  process.exit(0);
}
