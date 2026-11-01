-- Run AFTER supabase_schema.sql, and after adding yourself in Supabase -> Authentication -> Users.
-- Replace the email and name below with your own.
INSERT INTO profiles (user_id, email, full_name, role)
SELECT id, lower(email), 'Your Name', 'super_admin'
FROM auth.users
WHERE lower(email) = lower('you@example.com')
ON CONFLICT (user_id) DO UPDATE SET role = 'super_admin';

-- Check it worked (should return one row):
SELECT user_id, email, role FROM profiles;
