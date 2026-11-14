<?php
declare(strict_types=1);
const REBA_ADMIN_EMAIL = 'ahmadmdujan@gmail.com';
const REBA_RESET_FROM_EMAIL = 'info@rebabooksociety.websolve.co.in';
// Customer records must be stored outside the web server document root.
ini_set('session.use_strict_mode', '1');
ini_set('session.cookie_httponly', '1');
ini_set('session.cookie_samesite', 'Lax');
if (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') ini_set('session.cookie_secure', '1');
session_start();
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: strict-origin-when-cross-origin');
header('X-Frame-Options: DENY');

$books = [
 'perseus'=>['title'=>'Perseus the Deliverer','author'=>'Sri Aurobindo','category'=>'Drama','price'=>249,'isbn'=>'978-81-182748-5-8','image'=>'perseus-the-deliverer-front.jpg','description'=>'A lyrical retelling of the Greek myth of Perseus, brought to life in verse by Sri Aurobindo.'],
 'history'=>['title'=>'A History of English Literature','author'=>'Edward Albert','category'=>'Literary Studies','price'=>399,'isbn'=>'978-81-182748-1-0','image'=>'albert-front.jpg','description'=>'A companion to the people, periods and movements that shaped English literature.'],
 'justice'=>['title'=>'Justice','author'=>'John Galsworthy','category'=>'Drama','price'=>199,'isbn'=>'978-81-182372-7-3','image'=>'justice-front.jpg','description'=>'A powerful play that examines justice, compassion and the human cost of the law.'],
 'wasteland'=>['title'=>'The Waste Land and Other Poems','author'=>'T. S. Eliot','category'=>'Poetry','price'=>225,'isbn'=>'9788168868359','image'=>'the-waste-land-and-other-poems-front.jpg','description'=>'A collection of poems from one of the defining voices of modern literature.'],
 'biographia'=>['title'=>'Biographia Literaria','author'=>'S. T. Coleridge','category'=>'Literary Studies','price'=>299,'isbn'=>'978-81-995491-7-3','image'=>'biographia-literaria-front.jpg','description'=>'Coleridge’s reflections on imagination, poetry and the life of a writer, in a critical study.'],
 'awakening'=>['title'=>'The Awakening','author'=>'Kate Chopin','category'=>'Fiction','price'=>199,'isbn'=>'978-81-182748-4-1','image'=>'the-awakening-front.jpg','description'=>'Kate Chopin’s enduring novel of self-discovery, independence and the expectations of society.'],
 'old-man-and-the-sea'=>['title'=>'The Old Man and the Sea','author'=>'Ernest Hemingway','category'=>'Fiction','price'=>199,'isbn'=>'978-81-995491-5-9','image'=>'the-old-man-and-the-sea-front.jpg','description'=>'An ageing Cuban fisherman faces a great marlin in Hemingway’s enduring story of resilience and the sea.'],
];
function e($s): string { return htmlspecialchars((string)$s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); }
// SCRIPT_NAME points at the front controller, including any installation subdirectory.
$basePath = rtrim(str_replace('\\', '/', dirname($_SERVER['SCRIPT_NAME'] ?? '/index.php')), '/.');
function url($page='home', $args=[]): string {
 global $basePath;
 $path = $basePath.'/'.($page === 'home' ? '' : rawurlencode($page));
 if ($page === 'book' && isset($args['id'])) { $path .= '/'.rawurlencode((string)$args['id']); unset($args['id']); }
 $query = http_build_query($args);
 return $path.($query !== '' ? '?'.$query : '');
}
function asset($path): string { global $basePath; return $basePath.'/assets/'.$path; }
// Content-based versioning prevents a cached stylesheet from being paired with newer markup.
function stylesheet(): string {
 $file = __DIR__.'/assets/storefront.css';
 $version = is_file($file) ? substr(hash_file('sha256', $file), 0, 16) : 'missing';
 return asset('storefront.css').'?v='.$version;
}
function go($page='home', $args=[]): never { header('Location: '.url($page,$args)); exit; }
function csrf(): string { if (empty($_SESSION['csrf'])) $_SESSION['csrf']=bin2hex(random_bytes(32)); return $_SESSION['csrf']; }
function field(): string { return '<input type="hidden" name="csrf" value="'.e(csrf()).'">'; }
function flash($message): void { $_SESSION['flash']=$message; }
function db($callback) {
 // Refuse to create a fresh store while data from the old public/ layout remains in the web root.
 if (is_file(__DIR__.'/storage/data.json')) throw new RuntimeException('Move the legacy data file outside the document root before continuing; see README.');
 $path=getenv('REBA_STORAGE_DIR') ?: dirname(__DIR__).'/reba-book-society-data';
 if (!is_dir($path) && !mkdir($path,0700,true) && !is_dir($path)) throw new RuntimeException('Storage unavailable');
 $path=realpath($path); $root=realpath($_SERVER['DOCUMENT_ROOT'] ?? __DIR__);
 if (!$path || !$root || $path === $root || str_starts_with($path, rtrim($root, DIRECTORY_SEPARATOR).DIRECTORY_SEPARATOR)) throw new RuntimeException('Storage must be outside the document root.');
 $exists=is_file($path.'/data.json'); $fp=fopen($path.'/data.json','c+'); if (!$fp) throw new RuntimeException('Storage unavailable');
 chmod($path.'/data.json',0600); flock($fp, LOCK_EX); $raw=stream_get_contents($fp);
 if ($raw===false || ($raw==='' && $exists)) { flock($fp,LOCK_UN); fclose($fp); throw new RuntimeException('Customer data is empty or unreadable; restore it from a backup.'); }
 $data=$raw!=='' ? json_decode($raw,true) : ['users'=>[], 'orders'=>[], 'attempts'=>[]];
 if (!is_array($data)) { flock($fp,LOCK_UN); fclose($fp); throw new RuntimeException('Customer data is invalid; restore it from a backup.'); }
 $result=$callback($data); rewind($fp); ftruncate($fp,0); fwrite($fp,json_encode($data,JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE)); fflush($fp); flock($fp,LOCK_UN); fclose($fp); return $result;
}
function currentUser() {
 if (empty($_SESSION['user_id'])) return null;
 $user = db(function(&$d) {
  foreach ($d['users'] as $u) if ($u['id'] === $_SESSION['user_id']) return $u;
  return null;
 });
 if (!$user || (int)($user['auth_version'] ?? 0) !== (int)($_SESSION['auth_version'] ?? 0)) {
  unset($_SESSION['user_id'], $_SESSION['auth_version']);
  return null;
 }
 return $user;
}
function isAdmin($user): bool {
 return is_array($user) && ($user['is_admin'] ?? false) === true && strtolower($user['email'] ?? '') === REBA_ADMIN_EMAIL;
}
function available($book): bool { return ($book['stock'] ?? null) === null || $book['stock'] > 0; }
function passwordProblem($password): string {
 if (!is_string($password) || str_contains($password, "\0")) return 'Please enter a valid password.';
 // Avoid bcrypt's silent truncation while keeping the interface concise.
 if (strlen($password) > 72) return 'Please use a shorter password.';
 $length=preg_match_all('/./us', $password);
 if ($length === false) return 'Please enter a valid password.';
 return $length < 6 ? 'Minimum 6 Characters' : '';
}
function validNewPassword($password): bool { return passwordProblem($password) === ''; }
function resetConfig(): ?array {
 $base = rtrim(trim((string)getenv('REBA_BASE_URL')), '/');
 // Use the known live URL only on its exact host. Never construct a reset link from request headers.
 $host = strtolower((string)($_SERVER['HTTP_HOST'] ?? ''));
 if ($base === '' && in_array($host, ['rebabooksociety.websolve.co.in', 'rebabooksociety.websolve.co.in:443'], true)) $base = 'https://rebabooksociety.websolve.co.in';
 $from = REBA_RESET_FROM_EMAIL;
 $parts = parse_url($base);
 if (!filter_var($base, FILTER_VALIDATE_URL) || !is_array($parts) || ($parts['scheme'] ?? '') !== 'https' || empty($parts['host']) || isset($parts['user']) || isset($parts['pass']) || isset($parts['query']) || isset($parts['fragment']) || !filter_var($from, FILTER_VALIDATE_EMAIL) || str_contains($from, "\n") || str_contains($from, "\r") || !function_exists('mail')) return null;
 return ['base'=>$base, 'from'=>$from];
}
function clearResetTokens(array &$data, string $userId): void {
 $data['password_resets'] = array_filter($data['password_resets'] ?? [], fn($entry) => ($entry['user_id'] ?? '') !== $userId && ($entry['expires'] ?? 0) > time());
}
function cartCount(): int { return array_sum($_SESSION['cart'] ?? []); }
function money($n): string { return '₹'.number_format($n); }
function priceMarkup(array $book, bool $detail=false): string {
 $price=(int)$book['price']; $mrp=(int)($book['mrp']??$price);
 $html='<span class="price-display'.($detail?' price-display--detail':'').'"><strong class="price-current"><span class="sr-only">Selling price </span>'.e(money($price)).'</strong>';
 if ($mrp>0 && $price<$mrp) {
  $percent=round(($mrp-$price)*100/$mrp,1);
  if ($percent<=0) $label='<0.1';
  elseif ($percent>=100 && $price>0) $label='>99.9';
  else $label=rtrim(rtrim(number_format($percent,1,'.',''),'0'),'.');
  $html.='<span class="price-mrp">MRP <s>'.e(money($mrp)).'</s></span><span class="price-discount">'.e($label).'% off</span>';
 }
 return $html.'</span>';
}
function icon($name): string { $paths=['search'=>'<circle cx="11" cy="11" r="7"/><path d="m16 16 4 4"/>','user'=>'<circle cx="12" cy="8" r="3.5"/><path d="M5 20c0-4 3-6 7-6s7 2 7 6"/>','bag'=>'<path d="M5 8h14l1 12H4L5 8Z"/><path d="M9 9V6a3 3 0 0 1 6 0v3"/>','arrow'=>'<path d="M4 12h16M14 6l6 6-6 6"/>','heart'=>'<path d="M20.8 8.6c0 4-8.8 9.4-8.8 9.4S3.2 12.6 3.2 8.6a4.5 4.5 0 0 1 8.8-1.1 4.5 4.5 0 0 1 8.8 1.1Z"/>']; return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'.($paths[$name]??'').'</svg>'; }
// Persist catalogue changes alongside customer data; preserve edited and hidden books across deployments.
$allBooks=db(function(&$d) use($books) {
 if (!isset($d['products'])) $d['products']=[];
 foreach($books as $id=>$book) if (!array_key_exists($id,$d['products'])) { $book['mrp']=$book['price']; $book['stock']=null; $book['active']=true; $d['products'][$id]=$book; }
 foreach($d['products'] as &$book) if (!array_key_exists('mrp', $book)) $book['mrp']=$book['price'];
 unset($book);
 return $d['products'];
});
$books=array_filter($allBooks, fn($b)=>($b['active']??true) === true);
$removedFromCart=false;
foreach (($_SESSION['cart']??[]) as $id=>$qty) if (!isset($books[$id])) { unset($_SESSION['cart'][$id]); $removedFromCart=true; }
if ($removedFromCart) flash('An unavailable book was removed from your bag.');
$requestPath = rawurldecode(parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH) ?: '/');
$relativePath = $basePath !== '' && $requestPath === $basePath ? '/' : ($basePath !== '' && str_starts_with($requestPath, $basePath.'/') ? substr($requestPath, strlen($basePath)) : $requestPath);
$segments = explode('/', trim($relativePath, '/'));
$page = $segments[0] === '' || $segments[0] === 'index.php' ? 'home' : $segments[0];
if ($page === 'book' && count($segments) === 2 && $segments[1] !== '') $_GET['id'] = $segments[1];
elseif (count($segments) > 1) $page = 'not-found';
// Keep existing bookmarked query-string URLs working, but generate clean paths for all new links.
$legacy = ($relativePath === '/' || $relativePath === '/index.php') && isset($_GET['page']) && is_string($_GET['page']);
if ($legacy) {
 $page = $_GET['page'];
 if ($_SERVER['REQUEST_METHOD'] === 'GET') { $args = $_GET; unset($args['page']); header('Location: '.url($page, $args), true, 301); exit; }
}
// The homepage lives at the site root. Keep old homepage URLs as redirects.
if ($_SERVER['REQUEST_METHOD'] === 'GET' && !$legacy && (($basePath !== '' && $requestPath === $basePath) || in_array($relativePath, ['/home', '/home/', '/index.php'], true))) {
 header('Location: '.url('home', $_GET), true, 301); exit;
}
if ($_SERVER['REQUEST_METHOD'] === 'GET' && !$legacy && $relativePath !== '/' && str_ends_with($relativePath, '/')) {
 $query = $_GET; header('Location: '.url($page, $query), true, 301); exit;
}
// Old catalogue links on /home continue to work after moving the catalogue to /shop.
if ($_SERVER['REQUEST_METHOD'] === 'GET' && $page === 'home' && (isset($_GET['q']) || isset($_GET['category']))) { header('Location: '.url('shop', $_GET).'#collection', true, 301); exit; }
if ($page === 'reset-password') { header('Referrer-Policy: no-referrer'); header('Cache-Control: no-store, private'); }
$error='';
if ($_SERVER['REQUEST_METHOD']==='POST') {
 if (!hash_equals(csrf(), $_POST['csrf'] ?? '')) { http_response_code(403); exit('Invalid request. Please refresh the page and try again.'); }
 $action=$_POST['action'] ?? '';
 if ($action==='add') {
  $id=$_POST['id']??'';
  if (is_string($id) && isset($books[$id])) {
   $b=$books[$id]; $quantity=(int)($_SESSION['cart'][$id]??0);
   $limit=($b['stock']??null)===null ? 20 : min(20,(int)$b['stock']);
   $added=$quantity<$limit;
   if ($added) $_SESSION['cart'][$id]=++$quantity;
   $count=$quantity.' '.($quantity===1?'copy':'copies').' of this book '.($quantity===1?'is':'are').' in your cart.';
   $_SESSION['cart_feedback']=['message'=>$added ? '“'.$b['title'].'” was added to your cart. '.$count : '“'.$b['title'].'” could not be added: the available quantity or cart limit has been reached. '.$count, 'success'=>$added];
  } else $_SESSION['cart_feedback']=['message'=>'This book is no longer available.', 'success'=>false];
  $destination=($_POST['return']??'')==='book' && is_string($id) && isset($books[$id]) ? url('book',['id'=>$id]) : url(($_POST['return']??'')==='home' ? 'home' : 'shop');
  header('Location: '.$destination.'#cart-feedback'); exit;
 }
 if ($action==='update_cart') { foreach (($_POST['qty']??[]) as $id=>$qty) if(isset($books[$id],$_SESSION['cart'][$id])) { $n=max(0,min(20,(int)$qty)); if($n===0) unset($_SESSION['cart'][$id]); else $_SESSION['cart'][$id]=$n; } flash('Your bag has been updated.'); go('cart'); }
 if ($action==='logout') { $_SESSION=[]; session_destroy(); session_start(); session_regenerate_id(true); flash('You have signed out.'); go(); }
 if ($action==='register') {
  $name=trim($_POST['name']??''); $email=strtolower(trim($_POST['email']??'')); $password=$_POST['password']??'';
  if(mb_strlen_safe($name)<2 || strlen($name)>100 || !filter_var($email,FILTER_VALIDATE_EMAIL) || strlen($email)>254) $error='Please enter a valid name and email.';
  elseif (!validNewPassword($password)) $error=passwordProblem($password);
  else { $result=db(function(&$d) use($name,$email,$password) { foreach($d['users'] as $u) if($u['email']===$email) return false; $id=bin2hex(random_bytes(16)); $d['users'][]=['id'=>$id,'name'=>$name,'email'=>$email,'password'=>password_hash($password,PASSWORD_DEFAULT),'auth_version'=>0]; return $id; }); if(!$result) $error='An account with this email already exists.'; else { session_regenerate_id(true); $_SESSION['user_id']=$result; $_SESSION['auth_version']=0; flash('Welcome to the society.'); go(($_POST['next']??'')==='checkout' ? 'checkout' : 'account'); } }
 }
 if ($action==='login') {
  $email=strtolower(trim($_POST['email']??'')); $password=$_POST['password']??''; $key=hash('sha256',($_SERVER['REMOTE_ADDR']??'unknown').'|'.$email);
  $result=db(function(&$d) use($email,$password,$key) { $now=time(); $d['attempts']=array_filter($d['attempts'],fn($a)=>$a['time']>$now-900); $a=$d['attempts'][$key]??['count'=>0,'time'=>$now]; if($a['count']>=8) return 'locked'; $found=null; foreach($d['users'] as $u) if($u['email']===$email) { $found=$u; break; } if($found && password_verify($password,$found['password'])) { unset($d['attempts'][$key]); return ['id'=>$found['id'],'auth_version'=>(int)($found['auth_version']??0)]; } password_verify($password,'$2y$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2uheWG/igi.'); $d['attempts'][$key]=['count'=>$a['count']+1,'time'=>$now]; return false; });
  if(is_array($result)) { session_regenerate_id(true); $_SESSION['user_id']=$result['id']; $_SESSION['auth_version']=$result['auth_version']; flash('Welcome back.'); go(($_POST['next']??'')==='checkout' ? 'checkout' : 'account'); } $error=$result==='locked' ? 'Too many attempts. Please try again in 15 minutes.' : 'Email or password not recognised.';
 }
 if ($action==='save_profile') {
  $user=currentUser(); if (!$user) go('login');
  $name=trim((string)($_POST['name']??'')); $shipping=trim((string)($_POST['shipping_address']??'')); $billing=trim((string)($_POST['billing_address']??''));
  if (mb_strlen_safe($name)<2 || strlen($name)>100 || strlen($shipping)>1000 || strlen($billing)>1000) $error='Please enter a name of 2–100 characters and addresses of at most 1,000 characters.';
  else {
   $saved=db(function(&$d) use($user,$name,$shipping,$billing){foreach($d['users'] as &$u) if($u['id']===$user['id']) { if ((int)($u['auth_version']??0)!==(int)($user['auth_version']??0)) return false; $u['name']=$name; $u['shipping_address']=$shipping; $u['billing_address']=$billing; return true; } return false;});
   if (!$saved) { unset($_SESSION['user_id'],$_SESSION['auth_version']); go('login'); }
   flash('Your account details have been saved.'); go('account');
  }
 }
 if ($action==='change_password') {
  $user=currentUser(); if (!$user) go('login');
  $current=$_POST['current_password']??''; $new=$_POST['new_password']??''; $confirm=$_POST['confirm_password']??'';
  if (!validNewPassword($new)) $error=passwordProblem($new);
  elseif (!is_string($confirm) || !hash_equals($new,$confirm)) $error='New passwords do not match.';
  elseif (!is_string($current) || strlen($current)>4096) $error='Current password is incorrect.';
  else {
   $key=hash('sha256','change-password|'.$user['id'].'|'.($_SERVER['REMOTE_ADDR']??'unknown'));
   $result=db(function(&$d) use($user,$current,$new,$key) {
    $now=time(); $d['attempts']=array_filter($d['attempts']??[],fn($a)=>($a['time']??0)>$now-900);
    $a=$d['attempts'][$key]??['count'=>0,'time'=>$now]; if ($a['count']>=8) return 'locked';
    foreach($d['users'] as &$u) if($u['id']===$user['id']) {
     if ((int)($u['auth_version']??0)!==(int)($user['auth_version']??0)) return 'stale';
     if(!password_verify($current,$u['password'])) { $d['attempts'][$key]=['count'=>$a['count']+1,'time'=>$now]; return false; }
     $u['password']=password_hash($new,PASSWORD_DEFAULT); $u['auth_version']=(int)($u['auth_version']??0)+1;
     $version=$u['auth_version']; unset($d['attempts'][$key]); clearResetTokens($d,$u['id']); return $version;
    }
    return false;
   });
   if ($result==='stale') { unset($_SESSION['user_id'],$_SESSION['auth_version']); go('login'); }
   if (is_int($result)) { session_regenerate_id(true); $_SESSION['auth_version']=$result; flash('Your password has been updated. Other sessions have been signed out.'); go('account'); }
   $error=$result==='locked'?'Too many attempts. Please try again in 15 minutes.':'Current password is incorrect.';
  }
 }
 if ($action==='forgot_password') {
  $config=resetConfig(); $email=strtolower(trim((string)($_POST['email']??'')));
  if (!$config) $error='Password recovery email is not configured yet. Please contact the bookshop.';
  elseif (!filter_var($email,FILTER_VALIDATE_EMAIL) || strlen($email)>254) $error='Please enter a valid email address.';
  else {
   $token=bin2hex(random_bytes(32)); $hash=hash('sha256',$token); $ip=hash('sha256','reset-ip|'.($_SERVER['REMOTE_ADDR']??'unknown')); $emailKey=hash('sha256','reset-email|'.$email);
   $send=db(function(&$d) use($email,$hash,$ip,$emailKey) {
    $now=time(); $d['reset_limits']=array_filter($d['reset_limits']??[],fn($a)=>($a['time']??0)>$now-1800);
    $ipCount=$d['reset_limits'][$ip]['count']??0; $emailCount=$d['reset_limits'][$emailKey]['count']??0;
    if ($ipCount>=20 || $emailCount>=3) return false;
    foreach([$ip,$emailKey] as $key) { if (!isset($d['reset_limits'][$key])) $d['reset_limits'][$key]=['count'=>0,'time'=>$now]; $d['reset_limits'][$key]['count']++; }
    foreach($d['users'] as $u) if($u['email']===$email) { clearResetTokens($d,$u['id']); $d['password_resets'][$hash]=['user_id'=>$u['id'],'expires'=>$now+1800]; return true; }
    return false;
   });
   if ($send) {
    $link=$config['base'].'/reset-password?token='.$token;
    $body="A password reset was requested for your Reba Book Society account.\n\nOpen this link within 30 minutes:\n".$link."\n\nIf you did not request this, you can ignore this email.\n";
    if (!@mail($email,'Reset your Reba Book Society password',$body,"From: ".$config['from']."\r\nContent-Type: text/plain; charset=UTF-8")) error_log('Password reset email could not be sent; check mail configuration.');
   }
   flash('If an account exists for that email, a reset link will be sent.'); go('forgot-password');
  }
 }
 if ($action==='reset_password') {
  $token=$_POST['token']??''; $new=$_POST['new_password']??''; $confirm=$_POST['confirm_password']??'';
  if (!is_string($token) || !preg_match('/\A[a-f0-9]{64}\z/', $token)) $error='This reset link is invalid or has expired. Please request a new one.';
  elseif (!validNewPassword($new)) $error=passwordProblem($new);
  elseif (!is_string($confirm) || !hash_equals($new,$confirm)) $error='New passwords do not match.';
  else {
   $success=db(function(&$d) use($token,$new) {
    $hash=hash('sha256',$token); $entry=$d['password_resets'][$hash]??null;
    if (!$entry || ($entry['expires']??0)<=time()) { unset($d['password_resets'][$hash]); return false; }
    foreach($d['users'] as &$u) if($u['id']===$entry['user_id']) {
     $u['password']=password_hash($new,PASSWORD_DEFAULT); $u['auth_version']=(int)($u['auth_version']??0)+1; if (strtolower($u['email']??'')===REBA_ADMIN_EMAIL) $u['is_admin']=true; clearResetTokens($d,$u['id']); return true;
    }
    unset($d['password_resets'][$hash]); return false;
   });
   if ($success) { unset($_SESSION['user_id'],$_SESSION['auth_version']); session_regenerate_id(true); flash('Your password has been reset. Please sign in with your new password.'); go('login'); }
   $error='This reset link is invalid or has expired. Please request a new one.';
  }
 }
 if ($action==='admin_update' || $action==='admin_visibility') {
  $admin=currentUser(); if (!isAdmin($admin)) { http_response_code(403); exit('Access denied.'); }
  $id=$_POST['id']??''; $price=$_POST['price']??''; $mrp=$_POST['mrp']??''; $stock=$_POST['stock']??''; $visible=$_POST['visible']??'';
  if (!is_string($id) || !isset($allBooks[$id])) { http_response_code(404); exit('Book not found.'); }
  if ($action==='admin_update' && (!is_string($price) || !preg_match('/\A(?:0|[1-9][0-9]{0,6})\z/', $price) || !is_string($mrp) || !preg_match('/\A(?:0|[1-9][0-9]{0,6})\z/', $mrp) || (int)$price>(int)$mrp || !is_string($stock) || ($stock!=='' && !preg_match('/\A(?:0|[1-9][0-9]{0,5})\z/', $stock)))) $error='Enter whole-number prices with selling price no higher than MRP, and a non-negative whole-number stock count (or leave stock blank).';
  elseif ($action==='admin_visibility' && !in_array($visible,['0','1'],true)) $error='Invalid catalogue status.';
  else {
   $result=db(function(&$d) use($admin,$id,$action,$price,$mrp,$stock,$visible) {
    $authorized=false;
    foreach($d['users'] as $u) if($u['id']===$admin['id'] && isAdmin($u) && (int)($u['auth_version']??0)===(int)($_SESSION['auth_version']??0)) { $authorized=true; break; }
    if (!$authorized) return false;
    if (!isset($d['products'][$id])) return false;
    if ($action==='admin_update') { $d['products'][$id]['price']=(int)$price; $d['products'][$id]['mrp']=(int)$mrp; $d['products'][$id]['stock']=$stock==='' ? null : (int)$stock; }
    else $d['products'][$id]['active']=$visible==='1';
    return true;
   });
   if (!$result) { http_response_code(403); exit('Unable to update inventory.'); }
   flash($action==='admin_update' ? 'Inventory updated.' : ($visible==='1' ? 'Book restored to the shop.' : 'Book removed from the shop.'));
   go('admin');
  }
  $page='admin';
 }
 if ($action==='checkout') {
  $user=currentUser(); if(!$user) go('login'); $cart=$_SESSION['cart']??[]; $address=trim($_POST['address']??''); $phone=trim($_POST['phone']??'');
  if(!$cart) $error='Your bag is empty.';
  elseif(strlen($address)<10 || strlen($address)>1000 || !preg_match('/^[0-9+() -]{7,20}$/',$phone)) $error='Please provide a complete delivery address and a valid phone number.';
  else {
   // Validate the latest catalogue and reserve tracked stock under the same lock as order creation.
   $result=db(function(&$d) use($user,$cart,$address,$phone) {
    $authenticated=false; foreach($d['users'] as $u) if($u['id']===$user['id'] && (int)($u['auth_version']??0)===(int)($_SESSION['auth_version']??0)) { $authenticated=true; break; }
    if (!$authenticated) return 'session';
    $items=[]; $total=0;
    foreach($cart as $id=>$qty) {
     $b=$d['products'][$id]??null; $qty=(int)$qty;
     if (!$b || !($b['active']??true) || $qty<1 || $qty>20 || (($b['stock']??null)!==null && $qty>$b['stock'])) return 'stock';
     $items[]=['title'=>$b['title'],'price'=>$b['price'],'qty'=>$qty]; $total+=$b['price']*$qty;
    }
    if (!$items) return 'stock';
    foreach($cart as $id=>$qty) if (($d['products'][$id]['stock']??null)!==null) $d['products'][$id]['stock']-=(int)$qty;
    $d['orders'][]=['id'=>strtoupper(bin2hex(random_bytes(4))),'user_id'=>$user['id'],'date'=>date('Y-m-d H:i:s'),'items'=>$items,'total'=>$total,'address'=>$address,'phone'=>$phone,'status'=>'Order request received'];
    return 'ok';
   });
   if ($result==='session') { unset($_SESSION['user_id'],$_SESSION['auth_version']); go('login'); }
   if ($result==='stock') $error='A book in your bag is no longer available in the requested quantity. Please review your bag.';
   else { $_SESSION['cart']=[]; flash('Your order request has been received. No payment has been taken.'); go('account'); }
  }
 }
}
function mb_strlen_safe($s) { return function_exists('mb_strlen') ? mb_strlen($s) : strlen($s); }
if (!in_array($page, ['home','shop','about','contact','book','cart','login','register','checkout','account','admin','forgot-password','reset-password'], true) || ($page === 'book' && (!is_string($_GET['id'] ?? null) || !isset($books[$_GET['id']])))) { http_response_code(404); $page = 'not-found'; }
$user=currentUser(); if (in_array($page, ['account','checkout','admin'], true) && !$user) go('login'); if ($page==='admin' && !isAdmin($user)) { http_response_code(403); exit('Access denied.'); } $notice=$_SESSION['flash']??''; unset($_SESSION['flash']);
$cartFeedback=$_SESSION['cart_feedback']??null; unset($_SESSION['cart_feedback']);
function cartFeedback($feedback): void { if (!$feedback) return; ?><div id="cart-feedback" class="cart-feedback<?= $feedback['success']?'':' cart-feedback--error' ?>" role="status" tabindex="-1"><span><?= e($feedback['message']) ?></span><a href="<?= e(url('cart')) ?>">View cart →</a></div><?php }
function bookCard($id,$b,$index=0,$return='shop') { ?>
 <article class="book-card"><a class="book-image tone-<?= $index%6 ?>" href="<?= e(url('book',['id'=>$id])) ?>"><img src="<?= e(asset('covers/'.$b['image'])) ?>" alt="Cover of <?= e($b['title']) ?>"><span class="image-arrow">↗</span></a><div class="book-meta"><div><p class="book-category"><?= e($b['category']) ?></p><a href="<?= e(url('book',['id'=>$id])) ?>"><h3><?= e($b['title']) ?></h3></a><p class="author">by <?= e($b['author']) ?></p></div><?= priceMarkup($b) ?></div><form method="post" class="card-form"><?= field() ?><input type="hidden" name="action" value="add"><input type="hidden" name="id" value="<?= e($id) ?>"><input type="hidden" name="return" value="<?= e($return) ?>"><button type="submit" <?= available($b)?'':'disabled' ?>><?= available($b)?'Add to bag':'Out of stock' ?> <span><?= available($b)?'+':'' ?></span></button></form></article>
<?php }
?><!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="description" content="Discover thoughtfully selected books from Reba Book Society, College Street, Kolkata."><title>Reba Book Society | Books for curious minds</title><link rel="icon" href="<?= e(asset('favicon.ico')) ?>" sizes="any"><link rel="icon" type="image/png" sizes="512x512" href="<?= e(asset('favicon.png')) ?>"><link rel="apple-touch-icon" href="<?= e(asset('favicon.png')) ?>"><link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Libre+Baskerville:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet"><link rel="stylesheet" href="<?= e(stylesheet()) ?>"><?php if($page==='home'): ?><script src="<?= e(asset('featured-carousel.js').'?v='.substr(hash_file('sha256', __DIR__.'/assets/featured-carousel.js'), 0, 16)) ?>" defer></script><?php endif; ?></head><body>
<div class="announcement"><span>AN INDEPENDENT PUBLISHER &amp; BOOKSELLER</span><span class="announcement-right"><a class="announcement-icon" href="tel:+916289459775" aria-label="Call Reba Book Society"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6A19.79 19.79 0 0 1 2.12 4.18 2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72l.42 2.94a2 2 0 0 1-.57 1.72L7.69 9.65a16 16 0 0 0 6.66 6.66l1.27-1.27a2 2 0 0 1 1.72-.57l2.94.42A2 2 0 0 1 22 16.92z"/></svg></a><a class="announcement-icon" href="https://wa.me/916289459775" aria-label="Chat with Reba Book Society on WhatsApp"><svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z"/></svg></a><a class="announcement-number" href="tel:+916289459775">+91 6289459775</a></span></div>
<header class="header"><a href="<?= e(url()) ?>" class="brand" aria-label="Reba Book Society home"><img class="brand-logo" src="<?= e(asset('reba-logo.svg').'?v=wine') ?>" alt="Reba Book Society"></a><nav class="main-nav" aria-label="Main navigation"><a class="<?= $page==='home'?'active':'' ?>" <?= $page==='home'?'aria-current="page"':'' ?> href="<?= e(url()) ?>">Home</a><a class="<?= in_array($page,['shop','book'],true)?'active':'' ?>" <?= in_array($page,['shop','book'],true)?'aria-current="page"':'' ?> href="<?= e(url('shop')) ?>">Shop</a><a class="<?= $page==='about'?'active':'' ?>" <?= $page==='about'?'aria-current="page"':'' ?> href="<?= e(url('about')) ?>">About Us</a><a class="<?= $page==='contact'?'active':'' ?>" <?= $page==='contact'?'aria-current="page"':'' ?> href="<?= e(url('contact')) ?>">Contact</a></nav><div class="header-actions"><a href="<?= e(url('shop')) ?>#search" aria-label="Search books"><?= icon('search') ?></a><a href="<?= e(url($user?'account':'login')) ?>" aria-label="Your account"><?= icon('user') ?></a><a class="bag-link" href="<?= e(url('cart')) ?>" aria-label="Shopping bag"><?= icon('bag') ?><span><?= cartCount() ?></span></a></div></header>
<?php if($notice): ?><div class="notice"><?= e($notice) ?></div><?php endif; ?>
<main>
<?php if($page==='home'): ?>
<section class="hero"><div class="hero-copy"><div class="eyebrow"><span class="hero-line"></span> FROM COLLEGE STREET, WITH LOVE</div><h1>There’s always<br>another <em>story.</em></h1><p>Stories that travel, ideas that stay. Find your next great read from our corner of Kolkata.</p><div class="hero-buttons"><a class="button dark" href="<?= e(url('shop')) ?>">Browse the bookshop <?= icon('arrow') ?></a><a class="text-link" href="<?= e(url('about')) ?>">A little about us <span>↗</span></a></div></div><div class="hero-art"><img src="<?= e(asset('college-street.jpg')) ?>" alt="An illustrated scene of bookstalls and a tram on College Street"><div class="hero-image-caption"><span>THE WORLD OF REBA</span><span>COLLEGE STREET, KOLKATA &nbsp; ↗</span></div></div></section>
<div class="value-strip"><span>AN INDEPENDENT BOOKSHOP</span><span>GOOD BOOKS, CLOSE AT HAND</span><span>EST. IN THE CITY OF BOOKS</span></div>
<section class="collection section-wrap" id="collection"><div class="section-heading"><div><p class="overline">FROM OUR SHELVES</p><h2>A few good reads<span>.</span></h2><p>A small selection from our bookshop in Kolkata.</p></div><a class="under-link" href="<?= e(url('shop')) ?>">Explore all books <span>↗</span></a></div><?php cartFeedback($cartFeedback); ?><div class="book-grid featured-books" id="featured-books" tabindex="0" role="region" aria-label="Featured books"><?php $i=0; foreach(array_slice($books, 0, 4, true) as $id=>$b) bookCard($id,$b,$i++,'home'); ?></div><?php if(count($books)>1): ?><div class="featured-carousel-bar"><p>Swipe to explore</p><div class="featured-carousel-controls" hidden><button type="button" data-featured-prev aria-label="Previous featured book">←</button><button type="button" data-featured-next aria-label="Next featured book">→</button></div></div><?php endif; ?><p class="pricing-note">Prices shown are indicative starter prices and will be confirmed with your order request.</p><a class="button outline" href="<?= e(url('shop')) ?>">Visit the bookshop <?= icon('arrow') ?></a></section>
<section class="story-banner"><div class="story-visual"><div class="story-visual-inner"><img class="story-logo" src="<?= e(asset('reba-logo-light.svg')) ?>" alt="Reba Book Society"><span class="story-place">COLLEGE STREET<br>KOLKATA, INDIA</span></div></div><div class="story-copy"><p class="overline">OUR STORY</p><h2>From a street<br>that lives <em>for books.</em></h2><p>In Kolkata, College Street is more than a place. It’s a world of bookstalls, conversations and discoveries. That’s where you’ll find Reba Book Society, an independent publisher and bookseller.</p><a class="button outline" href="<?= e(url('about')) ?>">Get to know Reba <?= icon('arrow') ?></a></div></section>
<section class="closing"><span class="closing-rule"></span><p>FOR READERS, EVERYWHERE</p><h2>Stay curious. <em>Keep reading.</em></h2><a href="<?= e(url('shop')) ?>" class="under-link">Back to the books ↗</a></section>
<?php elseif($page==='shop'):
 $q=is_string($_GET['q']??null) ? trim($_GET['q']) : ''; $category=is_string($_GET['category']??null) ? $_GET['category'] : 'All books'; $filtered=array_filter($books,fn($b)=>($category==='All books'||$b['category']===$category) && ($q==='' || stripos($b['title'].' '.$b['author'].' '.$b['category'].' '.$b['isbn'],$q)!==false || (preg_match('/^[0-9 -]*[0-9][0-9 -]*$/', $q) && str_contains(str_replace('-', '', $b['isbn']), str_replace(['-', ' '], '', $q))))); ?>
<section class="collection section-wrap shop-page" id="collection"><div class="section-heading"><div><p class="overline">THE BOOKSHOP</p><h1>Find your next read<span>.</span></h1><p>Classics, poetry, drama and more, from our shelves to yours.</p></div></div><div class="shop-tools"><div class="filters"><?php foreach(['All books','Fiction','Poetry','Drama','Literary Studies'] as $c): ?><a class="<?= $category===$c?'selected':'' ?>" href="<?= e(url('shop',['category'=>$c,'q'=>$q])) ?>#collection"><?= e($c) ?></a><?php endforeach; ?></div><form class="search-form" method="get" action="<?= e(url('shop')) ?>"><input type="hidden" name="category" value="<?= e($category) ?>"><label for="search" class="sr-only">Search books</label><input id="search" name="q" placeholder="Search title, author or ISBN" value="<?= e($q) ?>"><button aria-label="Search"><?= icon('search') ?></button></form></div><div class="catalogue-line"><span>THE COLLECTION &nbsp; / &nbsp; <?= count($filtered) ?> <?= count($filtered) === 1 ? 'TITLE' : 'TITLES' ?></span></div><?php cartFeedback($cartFeedback); ?><div class="book-grid"><?php $i=0; foreach($filtered as $id=>$b) bookCard($id,$b,$i++); ?></div><?php if(!$filtered): ?><div class="empty">No books found. Try another search or category. <a href="<?= e(url('shop')) ?>#collection">View all books</a></div><?php endif; ?><p class="pricing-note">Prices shown are indicative starter prices and will be confirmed with your order request.</p></section>
<?php elseif($page==='book' && isset($books[$_GET['id']??''])): $id=$_GET['id']; $b=$books[$id]; ?>
<section class="inner section-wrap"><p class="breadcrumbs"><a href="<?= e(url()) ?>">Home</a> / <a href="<?= e(url('shop')) ?>">Books</a> / <?= e($b['title']) ?></p><div class="product-detail"><fieldset class="cover-gallery">
 <legend class="sr-only">Choose a cover image</legend>
 <input class="cover-toggle cover-toggle--front" type="radio" id="cover-front" name="cover-view" value="front" checked>
 <input class="cover-toggle cover-toggle--back" type="radio" id="cover-back" name="cover-view" value="back">
 <div class="cover-stage">
  <figure class="cover-view cover-view--front"><img src="<?= e(asset('covers/'.$b['image'])) ?>" alt="Front cover of <?= e($b['title']) ?>"></figure>
  <figure class="cover-view cover-view--back"><img src="<?= e(asset('covers/'.str_replace('-front.jpg','-back.jpg',$b['image']))) ?>" alt="Back cover of <?= e($b['title']) ?>"></figure>
 </div>
 <div class="cover-thumbnails">
  <label class="cover-thumb cover-thumb--front" for="cover-front"><img src="<?= e(asset('covers/'.$b['image'])) ?>" alt=""><span class="sr-only">Front cover</span></label>
  <label class="cover-thumb cover-thumb--back" for="cover-back"><img src="<?= e(asset('covers/'.str_replace('-front.jpg','-back.jpg',$b['image']))) ?>" alt=""><span class="sr-only">Back cover</span></label>
 </div>
 </fieldset><div class="detail-copy"><p class="overline"><?= e($b['category']) ?></p><h1><?= e($b['title']) ?></h1><p class="detail-author">by <?= e($b['author']) ?></p><p class="book-isbn detail-isbn">ISBN <?= e($b['isbn']) ?></p><?= priceMarkup($b,true) ?><p class="pricing-note">Indicative price. We’ll confirm the final price with your order request.</p><p class="description"><?= e($b['description']) ?></p><?php cartFeedback($cartFeedback); ?><form method="post"><?= field() ?><input type="hidden" name="action" value="add"><input type="hidden" name="id" value="<?= e($id) ?>"><input type="hidden" name="return" value="book"><button class="button dark" <?= available($b)?'':'disabled' ?>><?= available($b)?'Add to bag':'Out of stock' ?> <?= available($b)?icon('arrow'):'' ?></button></form><p class="detail-foot">A thoughtful read from our College Street shelves.</p></div></div></section>
<?php elseif($page==='cart'): $cart=$_SESSION['cart']??[]; $total=0; ?>
<section class="inner section-wrap narrow"><p class="overline">YOUR NEXT CHAPTER</p><h1>Your book bag<span class="italic">.</span></h1><p class="intro">A good story is just around the corner.</p><?php if(!$cart): ?><div class="empty">Your bag is waiting for a good book. <a href="<?= e(url('shop')) ?>">Explore the shelves ↗</a></div><?php else: ?><form method="post"><?= field() ?><input type="hidden" name="action" value="update_cart"><div class="cart-list"><?php foreach($cart as $id=>$qty): if(!isset($books[$id])) continue; $b=$books[$id]; $total+=$b['price']*$qty; ?><div class="cart-row"><img src="<?= e(asset('covers/'.$b['image'])) ?>" alt=""><div><h3><a href="<?= e(url('book',['id'=>$id])) ?>"><?= e($b['title']) ?></a></h3><p>by <?= e($b['author']) ?></p><p><?= money($b['price']) ?> each</p><?php if(($b['stock']??null)!==null && $qty>$b['stock']): ?><p class="stock-warning"><?= $b['stock']===0?'Out of stock':'Available: '.(int)$b['stock'] ?></p><?php endif; ?></div><label>Qty <input type="number" min="0" max="20" name="qty[<?= e($id) ?>]" value="<?= (int)$qty ?>"></label><strong><?= money($b['price']*$qty) ?></strong></div><?php endforeach; ?></div><p class="small">Set quantity to 0 to remove a book.</p><button class="button outline" type="submit">Update bag</button></form><div class="cart-total"><span>Indicative subtotal</span><strong><?= money($total) ?></strong></div><p class="pricing-note">Prices and delivery charges will be confirmed after you submit your order request. No payment is taken online.</p><a class="button dark" href="<?= e($user ? url('checkout') : url('login',['next'=>'checkout'])) ?>"><?= $user?'Continue to checkout':'Sign in to checkout' ?> <?= icon('arrow') ?></a><?php endif; ?></section>
<?php elseif(in_array($page,['login','register'])): ?><section class="inner section-wrap form-wrap"><p class="overline">THE REBA COMMUNITY</p><h1><?= $page==='login'?'Welcome back':'Join the society' ?><span class="italic">.</span></h1><p class="intro"><?= $page==='login'?'Sign in to see your orders and continue your story.':'Make an account to save your details and keep track of orders.' ?></p><?php if($error): ?><div class="error" role="alert"><?= e($error) ?></div><?php endif; ?><form method="post" class="form-stack"><?= field() ?><input type="hidden" name="action" value="<?= e($page) ?>"><input type="hidden" name="next" value="<?= e($_GET['next']??$_POST['next']??'') ?>"><?php if($page==='register'): ?><label>Full name<input name="name" required maxlength="100" autocomplete="name" value="<?= e($_POST['name']??'') ?>"></label><?php endif; ?><label>Email address<input type="email" name="email" required maxlength="254" autocomplete="email" value="<?= e($_POST['email']??'') ?>"></label><label>Password<input type="password" name="password" required minlength="6" <?= $page==='register'?'maxlength="72"':'' ?> autocomplete="<?= $page==='login'?'current-password':'new-password' ?>"><?php if($page==='register'): ?><small>Minimum 6 Characters</small><?php endif; ?></label><button class="button dark"><?= $page==='login'?'Sign in':'Create account' ?> <?= icon('arrow') ?></button></form><?php if($page==='login'): ?><p class="forgot-link"><a href="<?= e(url('forgot-password')) ?>">Forgot your password?</a></p><?php endif; ?><p class="form-switch"><?= $page==='login'?'New to Reba?':'Already a member?' ?> <a href="<?= e(url($page==='login'?'register':'login', ['next'=>$_GET['next']??$_POST['next']??''])) ?>"><?= $page==='login'?'Create an account':'Sign in' ?> ↗</a></p></section>
<?php elseif($page==='checkout'): if(!$user) { go('login'); } ?><section class="inner section-wrap form-wrap"><p class="overline">ALMOST THERE</p><h1>Checkout<span class="italic">.</span></h1><p class="intro">Tell us where your books should go.</p><div class="info-box">This submits an order request only. No payment is collected online; prices and delivery charges require confirmation.</div><?php if($error): ?><div class="error"><?= e($error) ?></div><?php endif; ?><form method="post" class="form-stack"><?= field() ?><input type="hidden" name="action" value="checkout"><label>Phone number<input name="phone" required maxlength="20" autocomplete="tel" value="<?= e($_POST['phone']??'') ?>"></label><label>Full delivery address<textarea name="address" required minlength="10" maxlength="1000" rows="4" autocomplete="street-address"><?= e($_POST['address']??$user['shipping_address']??'') ?></textarea></label><button class="button dark">Place order request <?= icon('arrow') ?></button></form><p class="small"><a href="<?= e(url('cart')) ?>">← Return to bag</a></p></section>
<?php elseif($page==='forgot-password'): ?><section class="inner section-wrap form-wrap"><p class="overline">ACCOUNT RECOVERY</p><h1>Forgot your password<span class="italic">?</span></h1><?php if($error): ?><div class="error" role="alert"><?= e($error) ?></div><?php endif; ?><?php if(resetConfig()): ?><p class="intro">Enter your account email and we’ll send a reset link if an account exists.</p><form method="post" class="form-stack"><?= field() ?><input type="hidden" name="action" value="forgot_password"><label>Email address<input type="email" name="email" required maxlength="254" autocomplete="email" value="<?= e($_POST['email']??'') ?>"></label><button class="button dark">Send reset link <?= icon('arrow') ?></button></form><?php else: ?><div class="info-box">Password recovery email is not configured yet. Please contact the bookshop for help.</div><?php endif; ?><p class="form-switch"><a href="<?= e(url('login')) ?>">← Back to sign in</a></p></section>
<?php elseif($page==='reset-password'): $resetToken=$_POST['token']??$_GET['token']??''; $validTokenFormat=is_string($resetToken) && preg_match('/\A[a-f0-9]{64}\z/', $resetToken); ?><section class="inner section-wrap form-wrap"><p class="overline">ACCOUNT RECOVERY</p><h1>Set a new password<span class="italic">.</span></h1><?php if($error): ?><div class="error" role="alert"><?= e($error) ?></div><?php endif; ?><?php if($validTokenFormat): ?><p class="intro">Choose a strong, unique password for your account.</p><form method="post" action="<?= e(url('reset-password')) ?>" class="form-stack"><?= field() ?><input type="hidden" name="action" value="reset_password"><input type="hidden" name="token" value="<?= e($resetToken) ?>"><label>New password<input type="password" name="new_password" required minlength="6" maxlength="72" autocomplete="new-password"><small>Minimum 6 Characters</small></label><label>Confirm new password<input type="password" name="confirm_password" required minlength="6" maxlength="72" autocomplete="new-password"></label><button class="button dark">Reset password <?= icon('arrow') ?></button></form><?php else: ?><div class="error">This reset link is invalid or has expired.</div><?php endif; ?><p class="form-switch"><a href="<?= e(url('forgot-password')) ?>">Request a new link</a></p></section>
<?php elseif($page==='account'): if(!$user) go('login'); $orders=db(function(&$d) use($user){return array_reverse(array_values(array_filter($d['orders'],fn($o)=>$o['user_id']===$user['id'])));}); ?><section class="inner section-wrap narrow"><div class="account-heading"><div><p class="overline">YOUR LITTLE CORNER</p><h1>Hello, <?= e(explode(' ',$user['name'])[0]) ?><span class="italic">.</span></h1><p class="intro"><?= e($user['email']) ?></p></div><form method="post"><?= field() ?><input type="hidden" name="action" value="logout"><button class="button outline">Sign out</button></form></div><?php if(isAdmin($user)): ?><p class="admin-account-link"><a class="button outline" href="<?= e(url('admin')) ?>">Manage inventory <?= icon('arrow') ?></a></p><?php elseif(strtolower($user['email']??'')===REBA_ADMIN_EMAIL): ?><div class="info-box">To activate administrator access, verify this email by <a href="<?= e(url('forgot-password')) ?>">resetting your password</a>.</div><?php endif; ?><h2>Your orders</h2><?php if(!$orders): ?><div class="empty">No orders yet. Your next favourite book is waiting. <a href="<?= e(url('shop')) ?>">Explore books ↗</a></div><?php else: foreach($orders as $order): ?><article class="order"><div class="order-head"><div><strong>Order #<?= e($order['id']) ?></strong><p><?= e(date('j M Y',strtotime($order['date']))) ?></p></div><span class="status"><?= e($order['status']) ?></span></div><?php foreach($order['items'] as $item): ?><p><?= e($item['title']) ?> × <?= (int)$item['qty'] ?> <span class="right"><?= money($item['price']*$item['qty']) ?></span></p><?php endforeach; ?><div class="order-total">Indicative subtotal <strong><?= money($order['total']) ?></strong></div><p class="small">No payment collected. Delivery and final prices require confirmation.</p></article><?php endforeach; endif; ?>
<div class="account-settings"><h2>Account settings</h2><?php if($error): ?><div class="error" role="alert"><?= e($error) ?></div><?php endif; ?><div class="settings-grid"><section class="settings-panel"><h3>Profile &amp; addresses</h3><p class="small">Your delivery address is filled in at checkout. Billing address is saved for your records.</p><form method="post" class="form-stack"><?= field() ?><input type="hidden" name="action" value="save_profile"><label>Display name<input name="name" required minlength="2" maxlength="100" autocomplete="name" value="<?= e(($_POST['action']??'')==='save_profile' ? ($_POST['name']??'') : $user['name']) ?>"></label><label>Delivery address<textarea name="shipping_address" maxlength="1000" rows="4" autocomplete="shipping street-address"><?= e(($_POST['action']??'')==='save_profile' ? ($_POST['shipping_address']??'') : ($user['shipping_address']??'')) ?></textarea></label><label>Billing address<textarea name="billing_address" maxlength="1000" rows="4" autocomplete="billing street-address"><?= e(($_POST['action']??'')==='save_profile' ? ($_POST['billing_address']??'') : ($user['billing_address']??'')) ?></textarea></label><button class="button outline">Save details</button></form></section><section class="settings-panel"><h3>Change password</h3><p class="small">For security, confirm your current password. Changing it signs out your other sessions.</p><form method="post" class="form-stack"><?= field() ?><input type="hidden" name="action" value="change_password"><label>Current password<input type="password" name="current_password" required autocomplete="current-password"></label><label>New password<input type="password" name="new_password" required minlength="6" maxlength="72" autocomplete="new-password"><small>Minimum 6 Characters</small></label><label>Confirm new password<input type="password" name="confirm_password" required minlength="6" maxlength="72" autocomplete="new-password"></label><button class="button outline">Update password</button></form></section></div></div></section>
<?php elseif($page==='admin'): ?><section class="inner section-wrap admin-page"><div class="admin-heading"><div><p class="overline">STORE MANAGEMENT</p><h1>Inventory<span class="italic">.</span></h1><p class="intro">Manage the books in your shop. Leave stock blank when you aren’t tracking a quantity.</p></div><a class="button outline" href="<?= e(url('account')) ?>">My account</a></div><?php if($error): ?><div class="error" role="alert"><?= e($error) ?></div><?php endif; ?><div class="info-box">Verify the starter prices before accepting requests. Tracked stock is reserved when an order request is placed. No payment is taken; update the count manually if a request is cancelled.</div><div class="inventory-list"><?php foreach($allBooks as $id=>$b): ?><article class="inventory-item"><div class="inventory-book"><img src="<?= e(asset('covers/'.$b['image'])) ?>" alt=""><div><h2><?= e($b['title']) ?></h2><p>by <?= e($b['author']) ?> · ISBN <?= e($b['isbn']) ?></p><span class="inventory-status"><?= ($b['active']??true)?'In shop':'Removed from shop' ?></span></div></div><form class="inventory-form" method="post"><?= field() ?><input type="hidden" name="action" value="admin_update"><input type="hidden" name="id" value="<?= e($id) ?>"><label>MRP (₹)<input type="number" name="mrp" min="0" max="9999999" step="1" required value="<?= (int)$b['mrp'] ?>"></label><label>Selling price (₹)<input type="number" name="price" min="0" max="9999999" step="1" required value="<?= (int)$b['price'] ?>"></label><label>Stock <span>(blank = untracked)</span><input type="number" name="stock" min="0" max="999999" step="1" value="<?= ($b['stock']??null)===null?'':(int)$b['stock'] ?>" placeholder="Untracked"></label><button class="button outline">Save</button></form><form method="post" class="inventory-visibility"><?= field() ?><input type="hidden" name="action" value="admin_visibility"><input type="hidden" name="id" value="<?= e($id) ?>"><input type="hidden" name="visible" value="<?= ($b['active']??true)?'0':'1' ?>"><button class="inventory-link"><?= ($b['active']??true)?'Remove from shop':'Restore to shop' ?></button></form></article><?php endforeach; ?></div></section>
<?php elseif($page==='about'): ?><section class="inner section-wrap about-page"><p class="overline">HELLO FROM KOLKATA</p><h1>For the love of<br><em>the written word.</em></h1><div class="about-grid"><div class="about-block"><img class="about-logo" src="<?= e(asset('reba-logo-light.svg')) ?>" alt="Reba Book Society"><p>INDEPENDENT BOOKSELLER<br>COLLEGE STREET, KOLKATA</p></div><div><h2>A little about us.</h2><p>Reba Book Society is a publisher and bookseller located in College Street, Kolkata—a place where a love of books is always close at hand.</p><p>We believe the best books stay with you. From timeless literature to poetry and drama, our shelves are made for readers, collectors and the endlessly curious.</p><div id="visit"><p class="overline">COME SAY HELLO</p><h2>Find us on College Street.</h2><p>Stall No. 89, College Street<br>(Near Calcutta University)<br>Kolkata - 700009</p></div><a class="button dark" href="<?= e(url('shop')) ?>">Explore our books <?= icon('arrow') ?></a></div></div></section>
<?php elseif($page==='contact'): ?><section class="inner section-wrap narrow"><p class="overline">GET IN TOUCH &nbsp; / &nbsp; REBA BOOK SOCIETY</p><h1>Contact us<span class="italic">.</span></h1><p class="intro">We’d love to hear from you or welcome you to our bookshop.</p><div class="contact-details"><div><h2>Mobile / WhatsApp No.</h2><a href="tel:+916289459775">+91 6289459775</a><a class="contact-whatsapp" href="https://wa.me/916289459775">Chat on WhatsApp <?= icon('arrow') ?></a></div><div><h2>Visit us</h2><address>Stall No. 89, College Street<br>(Near Calcutta University)<br>Kolkata - 700009</address></div></div><a class="button outline" href="<?= e(url('about')) ?>#visit">More about our bookshop <?= icon('arrow') ?></a></section>
<?php else: http_response_code(404); ?><section class="inner section-wrap narrow"><h1>Page not found<span class="italic">.</span></h1><p>Let’s get you back to the books.</p><a class="button dark" href="<?= e(url()) ?>">Back home <?= icon('arrow') ?></a></section><?php endif; ?>
</main><footer><div class="footer-main"><div><a href="<?= e(url()) ?>" class="brand footer-brand"><img class="brand-logo" src="<?= e(asset('reba-logo-light.svg')) ?>" alt="Reba Book Society"></a><p>An independent publisher and bookseller<br>from College Street, Kolkata.</p></div><div><h4>EXPLORE</h4><a href="<?= e(url('shop')) ?>">Shop All Books</a><a href="<?= e(url('about')) ?>">Our Story</a><a href="<?= e(url('about')) ?>#visit">Visit Us</a><a href="<?= e(url('contact')) ?>">Contact</a></div><div><h4>YOUR ACCOUNT</h4><a href="<?= e(url($user?'account':'login')) ?>">My Account</a><a href="<?= e(url('account')) ?>">My Orders</a><a href="<?= e(url('cart')) ?>">Shopping Bag</a><?php if(isAdmin($user)): ?><a href="<?= e(url('admin')) ?>">Manage Inventory</a><?php endif; ?></div><div class="footer-note"><h4>A NOTE FOR READERS</h4><p>Good books have a way of<br>bringing people together.</p><span>BOOKS &amp; IDEAS SINCE ALWAYS</span></div></div><div class="footer-bottom"><span>© <?= date('Y') ?> REBA BOOK SOCIETY</span><span>AN INDEPENDENT BOOKSHOP IN KOLKATA, INDIA</span><span>MADE FOR READERS, EVERYWHERE</span></div></footer></body></html>
