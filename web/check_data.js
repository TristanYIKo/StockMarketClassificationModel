

const { createClient } = require('@supabase/supabase-js');
const fs = require('fs');
const path = require('path');
const dns = require('node:dns');
if (dns.setDefaultResultOrder) {
    dns.setDefaultResultOrder('ipv4first');
}


// Read .env.local manually
const envPath = path.join(__dirname, '.env.local');
const envContent = fs.readFileSync(envPath, 'utf8');

let url = '';
let key = '';

envContent.split('\n').forEach(line => {
    if (line.startsWith('NEXT_PUBLIC_SUPABASE_URL=')) {
        url = line.split('=')[1].trim();
    }
    if (line.startsWith('NEXT_PUBLIC_SUPABASE_KEY=')) {
        key = line.split('=')[1].trim();
    }
});

console.log('URL:', url);
console.log('KEY Length:', key.length);

const supabase = createClient(url, key);

async function test() {
    console.log('Fetching predictions...');
    const { data, error } = await supabase
        .from('model_predictions_classification')
        .select('*')
        .limit(2);

    if (error) {
        console.error('Error:', error);
    } else {
        console.log('Data:', data);
    }
}

test();
