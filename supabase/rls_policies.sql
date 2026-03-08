-- Apply in Supabase SQL Editor
-- 1) Enable RLS on articles table
ALTER TABLE public.articles ENABLE ROW LEVEL SECURITY;

-- 2) Public read access
DROP POLICY IF EXISTS "public_can_read_articles" ON public.articles;
CREATE POLICY "public_can_read_articles"
ON public.articles
FOR SELECT
TO anon, authenticated
USING (true);

-- 3) Everyone can insert (online add)
DROP POLICY IF EXISTS "public_can_insert_articles" ON public.articles;
CREATE POLICY "public_can_insert_articles"
ON public.articles
FOR INSERT
TO anon, authenticated
WITH CHECK (true);

-- 4) Only admin can update
-- Replace with your real admin email
DROP POLICY IF EXISTS "admin_only_update_articles" ON public.articles;
CREATE POLICY "admin_only_update_articles"
ON public.articles
FOR UPDATE
TO authenticated
USING (lower(auth.jwt() ->> 'email') = 'your-admin-email@example.com')
WITH CHECK (lower(auth.jwt() ->> 'email') = 'your-admin-email@example.com');

-- 5) Only admin can delete
-- Replace with your real admin email
DROP POLICY IF EXISTS "admin_only_delete_articles" ON public.articles;
CREATE POLICY "admin_only_delete_articles"
ON public.articles
FOR DELETE
TO authenticated
USING (lower(auth.jwt() ->> 'email') = 'your-admin-email@example.com');
