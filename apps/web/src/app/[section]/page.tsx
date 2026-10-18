import Link from "next/link";
import { notFound } from "next/navigation";
import { sectionDescriptions } from "@/lib/navigation";
import styles from "./section.module.css";

export default async function SectionPage({ params }: { params: Promise<{ section: string }> }) {
  const { section } = await params;
  const details = sectionDescriptions[section];
  if (!details) notFound();

  return (
    <section className={styles.page}>
      <p className={styles.eyebrow}>MILESTONE {details.milestone} · IN DEVELOPMENT</p>
      <h1>{details.title}<span> / {details.english}</span></h1>
      <div className={styles.statusLine}>
        <span aria-hidden="true" />
        <strong>Chưa có dữ liệu hoặc workflow khả dụng tại milestone này.</strong>
      </div>
      <p className={styles.bodyCopy}>
        Khu vực này sẽ chỉ hiển thị dữ liệu sau khi API và acceptance checks tương ứng được hoàn thành. Không có dữ liệu demo thay thế.
      </p>
      <Link className={styles.backLink} href="/">← Về tổng quan</Link>
    </section>
  );
}