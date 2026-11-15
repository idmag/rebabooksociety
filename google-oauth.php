<?php
declare(strict_types=1);

// A private JSON file supports shared hosts that cannot set PHP environment variables.
// It lives beside the customer data, never in the website directory.
function googlePrivateConfig(): array {
 $path=getenv('REBA_STORAGE_DIR') ?: dirname(__DIR__).'/reba-book-society-data';
 $directory=realpath($path); $root=realpath($_SERVER['DOCUMENT_ROOT']??__DIR__);
 if (!$directory || !$root || !is_dir($directory) || $directory===$root || str_starts_with($directory,rtrim($root,DIRECTORY_SEPARATOR).DIRECTORY_SEPARATOR)) return [];
 $file=$directory.'/google-config.json';
 if (is_link($file) || !is_file($file) || realpath($file)!==$file || !is_readable($file)) return [];
 $size=filesize($file);
 if ($size===false || $size>8192) return [];
 $contents=@file_get_contents($file);
 if (!is_string($contents)) return [];
 $config=json_decode($contents,true);
 return is_array($config) ? $config : [];
}
// OAuth configuration is private server configuration, never browser supplied.
function googleConfig(): ?array {
 $id=trim((string)getenv('REBA_GOOGLE_CLIENT_ID'));
 $secret=trim((string)getenv('REBA_GOOGLE_CLIENT_SECRET'));
 $base=trim((string)getenv('REBA_BASE_URL'));
 // Use an entire configuration source, never mix credentials from different clients.
 if ($id==='' || $secret==='' || $base==='') {
  $config=googlePrivateConfig();
  $id=is_string($config['client_id']??null)?trim($config['client_id']):'';
  $secret=is_string($config['client_secret']??null)?trim($config['client_secret']):'';
  $base=is_string($config['base_url']??null)?trim($config['base_url']):'';
 }
 $base=rtrim($base, '/');
 $parts=parse_url($base);
 if (!preg_match('/\A[0-9]+-[a-zA-Z0-9_-]+\.apps\.googleusercontent\.com\z/', $id) || $secret==='' || strlen($secret)>1024 || preg_match('/[\r\n]/', $secret) || !filter_var($base,FILTER_VALIDATE_URL) || !is_array($parts) || ($parts['scheme']??'')!=='https' || empty($parts['host']) || isset($parts['user']) || isset($parts['pass']) || isset($parts['query']) || isset($parts['fragment']) || !function_exists('curl_init')) return null;
 return ['id'=>$id,'secret'=>$secret,'redirect'=>$base.'/google-callback'];
}
function googleRequest(string $url, array $headers, ?array $post=null): ?array {
 // Only fixed Google endpoints are ever used. Follow no redirects with credentials.
 if (!in_array($url,['https://oauth2.googleapis.com/token','https://openidconnect.googleapis.com/v1/userinfo'],true)) return null;
 $ch=curl_init($url);
 $options=[CURLOPT_RETURNTRANSFER=>true,CURLOPT_FOLLOWLOCATION=>false,CURLOPT_CONNECTTIMEOUT=>5,CURLOPT_TIMEOUT=>12,CURLOPT_HTTPHEADER=>$headers,CURLOPT_SSL_VERIFYPEER=>true,CURLOPT_SSL_VERIFYHOST=>2];
 if ($post!==null) { $options[CURLOPT_POST]=true; $options[CURLOPT_POSTFIELDS]=http_build_query($post,'','&',PHP_QUERY_RFC3986); }
 curl_setopt_array($ch,$options);
 $body=curl_exec($ch); $status=curl_getinfo($ch,CURLINFO_HTTP_CODE); curl_close($ch);
 if (!is_string($body) || strlen($body)>65536 || $status!==200) return null;
 $result=json_decode($body,true);
 return is_array($result) ? $result : null;
}
function googleIdentity(array $profile): ?array {
 $sub=$profile['sub']??null; $email=$profile['email']??null;
 if (!is_string($sub) || !preg_match('/\A[a-zA-Z0-9._-]{1,255}\z/', $sub) || !is_string($email) || strlen($email)>254 || !filter_var($email,FILTER_VALIDATE_EMAIL) || ($profile['email_verified']??false)!==true) return null;
 $name=$profile['name']??'';
 if (!is_string($name) || strlen($name)>100 || strlen(trim($name))<2 || preg_match('/[\x00-\x1f\x7f]/', $name)) $name='Reader';
 return ['sub'=>$sub,'email'=>strtolower($email),'name'=>trim($name)];
}
// No email-only account linking: the owner must first sign in to their existing account.
function googleAccount(array &$data, array $identity, ?array $link): array {
 $users=&$data['users'];
 foreach ($users as $user) if (($user['google_sub']??null)===$identity['sub']) {
  if ($link!==null && ($user['id']!==$link['id'] || (int)($user['auth_version']??0)!==$link['auth_version'])) return ['error'=>'This Google account is already linked to another account.'];
  return ['id'=>$user['id'],'auth_version'=>(int)($user['auth_version']??0),'linked'=>$link!==null];
 }
 if ($link!==null) {
  foreach ($users as &$user) if ($user['id']===$link['id']) {
   if ((int)($user['auth_version']??0)!==$link['auth_version']) return ['error'=>'Your session changed. Please sign in again.'];
   if (!empty($user['google_sub'])) return ['error'=>'A Google account is already linked to this account.'];
   if (strtolower($user['email'])!==$identity['email']) return ['error'=>'The Google email must match your existing account email.'];
   $user['google_sub']=$identity['sub'];
   return ['id'=>$user['id'],'auth_version'=>(int)($user['auth_version']??0),'linked'=>true];
  }
  return ['error'=>'Your session changed. Please sign in again.'];
 }
 foreach ($users as $user) if (strtolower($user['email'])===$identity['email']) return ['error'=>'An account with this email already exists. Sign in with your password and link Google from your account settings.'];
 $id=bin2hex(random_bytes(16));
 $users[]=['id'=>$id,'name'=>$identity['name'],'email'=>$identity['email'],'password'=>password_hash(bin2hex(random_bytes(32)),PASSWORD_DEFAULT),'google_sub'=>$identity['sub'],'google_only'=>true,'auth_version'=>0];
 return ['id'=>$id,'auth_version'=>0,'linked'=>false];
}
