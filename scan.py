#!/usr/bin/python3
import os,argparse,glob,subprocess,sqlite3
import xxhash,magic

def calc_hash_from_file_handle(f):
    h = xxhash.xxh64()
    bufsize = h.block_size * 0x800
    data = f.read(bufsize)
    while data:
        h.update(data)
        data = f.read(bufsize)
    return h.hexdigest()

def calc_hash(filename):
    with open(filename, "rb") as f:
        return calc_hash_from_file_handle(f)

def create_thumbnail(video, thumbnail):
    subprocess.call(["ffmpeg", "-y", "-loglevel", "fatal", "-ss", "00:05:00.00", "-i", video, "-vf", "scale=160:160:force_original_aspect_ratio=decrease", "-vframes", "1", thumbnail])

def main(dbfile,path):
    db = sqlite3.connect(dbfile)
    cnt = 0
    thumbnail_dir = os.path.join(path, "thumbnail")
    os.makedirs(thumbnail_dir,exist_ok=True)
    try:
        cur = db.cursor()
        cur.execute("create table if not exists objects(hash text primary key,size integer not null,rating integer default 0 not null)")
        cur.execute("create table if not exists files(filename text primary key,hash text not null,mtime real not null)")
        cur.execute("create index if not exists files_idx on files(hash)")

        print("Detecting deleted files...")
        cur.execute("select filename from files")
        files_to_be_deleted = []
        for row in cur:
            filename = row[0]
            if not os.path.exists(os.path.join(path,filename)):
                files_to_be_deleted.append(filename)
        for filename in files_to_be_deleted:
            cur.execute("delete from files where filename=?", (filename,))
            print("%s is deleted." % (filename,))
        db.commit()
        print("Done.  Scanning files...")

        for p in glob.iglob(os.path.join(path, "**", "*"), recursive=True):
            if not os.path.isfile(p) or os.path.islink(p): continue
            #else
            filename = os.path.relpath(p, path)
            mtime = os.path.getmtime(p)
            cur.execute("select count(*) from files where filename=? and mtime>=?", (filename,mtime))
            if cur.fetchone()[0] > 0: continue
            #else
            if not magic.from_file(p, mime=True).startswith("video/"): continue
            #else
            size = os.path.getsize(p)
            hash = calc_hash(p)
            cur.execute("select count(*) from objects where hash=?", (hash,))
            is_new = cur.fetchone()[0] == 0
            if is_new:
                create_thumbnail(p, os.path.join(thumbnail_dir, hash + ".jpg"))
                cur.execute("insert or ignore into objects(hash,size) values(?,?)", (hash,size))

            cur.execute("insert or replace into files(filename,hash,mtime) values(?,?,?)", (filename,hash,mtime))
            print(filename, size, hash, mtime, is_new)

            db.commit()
            cnt += 1
        
        files_to_be_deleted = []

        print("Searching duped files...")
        hashes_duped = []
        cur.execute("select hash as cnt from files group by hash having count(hash) > 0")
        for row in cur:
            hashes_duped.append(row[0])
        for hash in hashes_duped:
            cur.execute("select filename from files where hash=? order by mtime", (hash,))
            first = True
            for row in cur:
                if not first: files_to_be_deleted.append(row[0])
                first = False

        print("Searching underrated files...")
        cur.execute("select filename from files,objects where files.hash=objects.hash and rating < 0")
        for row in cur:
            files_to_be_deleted.append(row[0])

        for filename in files_to_be_deleted:
            cur.execute("delete from files where filename=?", (filename,))
            file_to_delete = os.path.join(path,filename)
            if os.path.isfile(file_to_delete): os.unlink(file_to_delete)
            print("%s is deleted." % (filename,))
            db.commit()
        
        print("Done")
    finally:
        db.close()
    return cnt

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("dbfile")
    parser.add_argument("path")
    args = parser.parse_args()
    cnt = main(args.dbfile,args.path)
    print("%d files scanned." % cnt)
