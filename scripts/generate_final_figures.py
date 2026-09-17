#!/usr/bin/env python3
"""Generate presentation-safe figures from the published real-data priority outputs.

The script intentionally uses plain-language labels in figures. Technical source names
(THOR and KH-9) appear only as parenthetical provenance, not as the primary concept.
No figure claims calibrated P(UXO) or field verification.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd

INK="#1C3557"; BLUE="#4C7FB0"; MINT="#5FA383"; BLUSH="#C9705C"; CREAM="#DFC58A"; GRID="#E4ECF4"
CLASS_COLORS=["#fff7bc","#fee391","#fdae61","#f46d43","#b2182b"]


def plt_setup():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "figure.dpi":130,"savefig.dpi":160,"font.size":9.5,
        "axes.edgecolor":"#9DBCDA","axes.labelcolor":INK,"text.color":INK,
        "xtick.color":INK,"ytick.color":INK,"axes.grid":True,"grid.color":GRID,
        "grid.linewidth":.8,"figure.facecolor":"white","savefig.facecolor":"white",
    })
    return plt


def save(fig, path, *, bottom=.05, right=.98, top=.94):
    path=Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(rect=(.02,bottom,right,top))
    fig.savefig(path,bbox_inches="tight",pad_inches=.18)


def load_grid(data_dir:Path):
    obj=json.loads((data_dir/"priority_grid_compact.json").read_text(encoding="utf-8"))
    schema=obj["schema"]
    df=pd.DataFrame(obj["rows"],columns=schema)
    return df,obj["class_labels"]


def arrays(df):
    min_e,max_e=int(df.e.min()),int(df.e.max()); min_n,max_n=int(df.n.min()),int(df.n.max())
    shape=(max_n-min_n+1,max_e-min_e+1)
    def arr(col):
        a=np.full(shape,np.nan,float)
        x=(df.e-min_e).astype(int).to_numpy(); y=(df.n-min_n).astype(int).to_numpy()
        a[y,x]=df[col].to_numpy(float); return a
    return shape,min_e,min_n,arr


def fig_concentration(df,out):
    plt=plt_setup(); s=np.sort(df.priority.to_numpy(float))[::-1]
    area=np.arange(1,len(s)+1)/len(s); cumulative=np.cumsum(s)/s.sum()
    i20=max(0,int(np.ceil(.20*len(s)))-1); y20=100*cumulative[i20]
    fig,ax=plt.subplots(figsize=(6.8,5.0))
    ax.plot(area*100,cumulative*100,color=INK,lw=2.3,label="Xếp theo chỉ số ưu tiên")
    ax.plot([0,100],[0,100],color=BLUSH,ls="--",lw=1.4,label="Phân bố đều theo diện tích")
    ax.axvline(20,color=CREAM,ls=":",lw=1.2); ax.scatter([20],[y20],s=55,color=MINT,edgecolor="white",lw=.8,zorder=5)
    ax.annotate(f"Top 20% diện tích\nbao phủ {y20:.1f}% tổng bằng chứng",xy=(20,y20),xytext=(38,max(14,y20-22)),
                arrowprops=dict(arrowstyle="->",color=MINT,lw=1.2),bbox=dict(boxstyle="round,pad=.3",fc="white",ec="#DDE6EF",alpha=.95))
    ax.set(xlim=(0,100),ylim=(0,100),xlabel="Tỉ lệ diện tích được ưu tiên (%)",ylabel="Tỉ lệ tổng bằng chứng lịch sử được bao phủ (%)",
           title="Mức tập trung bằng chứng lịch sử theo diện tích ưu tiên")
    ax.legend(frameon=False,loc="upper center",bbox_to_anchor=(.5,-.15),ncol=2,fontsize=8.4)
    save(fig,out,bottom=.14); plt.close(fig)


def marker(ax,x,y,labels=None,nlabel=6):
    ax.scatter(x,y,s=118,fc="white",ec="white",lw=0,zorder=6)
    ax.scatter(x,y,s=72,fc="#53D8FB",ec="#08306B",lw=1.4,zorder=7)
    ax.scatter(x,y,s=13,fc="#08306B",ec="white",lw=.4,zorder=8)
    if labels is not None:
        for i,(xx,yy,lab) in enumerate(zip(x,y,labels)):
            if i>=nlabel: break
            ax.text(xx+2,yy+2,str(lab),fontsize=8.0,color="#08306B",weight="bold",
                    bbox=dict(boxstyle="round,pad=.16",fc="white",ec="none",alpha=.9),zorder=9)


def fig_map(df,top,out):
    plt=plt_setup(); shape,min_e,min_n,arr=arrays(df); z=arr("priority")
    fig,ax=plt.subplots(figsize=(9.0,6.1)); vmax=float(np.nanquantile(z,.995))
    im=ax.imshow(z,origin="lower",cmap="YlOrRd",vmin=0,vmax=vmax,interpolation="nearest")
    t=top.head(15); x=(t.e-min_e).to_numpy(); y=(t.n-min_n).to_numpy()
    marker(ax,x,y,labels=None,nlabel=0)
    cb=fig.colorbar(im,ax=ax,fraction=.034,pad=.025); cb.set_label("Chỉ số ưu tiên tương đối (0–1)")
    from matplotlib.lines import Line2D
    h=Line2D([0],[0],marker='o',color='none',label='Khu vực ưu tiên cao',markerfacecolor='#53D8FB',markeredgecolor='#08306B',markersize=7.2,markeredgewidth=1.2)
    fig.legend(handles=[h],loc="center right",bbox_to_anchor=(.985,.83),frameon=False,fontsize=8.5)
    ax.set_title("Bản đồ ưu tiên khảo sát",pad=10); ax.set_xlabel("Ô lưới theo hướng đông"); ax.set_ylabel("Ô lưới theo hướng bắc"); ax.grid(False)
    fig.text(.47,.024,"Điểm đánh dấu là tâm ô phân tích ưu tiên — không phải vị trí vật nổ đã được xác nhận.",ha="center",fontsize=8.4,color=INK)
    save(fig,out,bottom=.09,right=.88); plt.close(fig)


def fig_sources(df,out):
    plt=plt_setup(); shape,_,_,arr=arrays(df)
    layers=[("thor","Hồ sơ không kích giải mật\n(nguồn THOR)","Blues"),("kh9","Dấu vết hố bom lịch sử\n(ảnh KH-9)","Greens"),("priority","Chỉ số ưu tiên tổng hợp","YlOrRd")]
    fig,axes=plt.subplots(1,3,figsize=(12.0,4.25))
    for ax,(col,title,cmap) in zip(axes,layers):
        a=arr(col); vmax=float(np.nanquantile(a,.995)); ax.imshow(a,origin="lower",cmap=cmap,vmin=0,vmax=max(vmax,1e-9),interpolation="nearest")
        ax.set_title(title,fontsize=9.5,pad=10); ax.set_xticks([]); ax.set_yticks([]); ax.grid(False)
    fig.suptitle("Ba lớp thông tin trên cùng vùng nghiên cứu",fontsize=12.5,y=.985)
    fig.text(.5,.035,"Hai nguồn bằng chứng lịch sử độc lập được chuẩn hóa về cùng lưới 100 m trước khi tổng hợp.",ha="center",fontsize=8.5,color=INK)
    save(fig,out,bottom=.08,top=.86); plt.close(fig)


def fig_distribution(df,labels,out):
    plt=plt_setup(); counts=df["class"].value_counts().to_dict(); vals=[int(counts.get(i,0)) for i in range(len(labels))]
    fig,ax=plt.subplots(figsize=(7.0,4.6)); bars=ax.bar(labels,vals,color=CLASS_COLORS[:len(labels)])
    total=sum(vals)
    for b,v in zip(bars,vals):
        ax.text(b.get_x()+b.get_width()/2,b.get_height()+total*.007,f"{v:,}\n({v/total*100:.1f}%)",ha="center",va="bottom",fontsize=8.2)
    ax.set_title("Phân bố mức ưu tiên trong vùng nghiên cứu"); ax.set_ylabel("Số ô lưới"); ax.set_xlabel("Mức ưu tiên"); ax.margins(y=.18)
    save(fig,out); plt.close(fig)


def fig_components(top,out):
    plt=plt_setup(); d=top.head(8); x=np.arange(len(d)); a=.5*d.thor.to_numpy(float); b=.5*d.kh9.to_numpy(float)
    fig,ax=plt.subplots(figsize=(7.2,4.6)); ax.bar(x,a,color=BLUE,label="Hồ sơ không kích giải mật (50%)"); ax.bar(x,b,bottom=a,color=MINT,label="Dấu vết hố bom lịch sử (50%)")
    for xx,v in zip(x,a+b): ax.text(xx,v+.008,f"{v:.3f}",ha="center",fontsize=8)
    ax.set_xticks(x); ax.set_xticklabels([f"#{int(v)}" for v in d["rank"]]); ax.set_ylim(0,1.07); ax.set_xlabel("Khu vực theo thứ hạng"); ax.set_ylabel("Chỉ số ưu tiên")
    ax.set_title("Điểm ưu tiên được hình thành từ hai nguồn bằng chứng như thế nào?")
    ax.legend(frameon=False,loc="upper center",bbox_to_anchor=(.5,-.16),ncol=2,fontsize=8.2)
    save(fig,out,bottom=.14); plt.close(fig)


def fig_top(top,out):
    plt=plt_setup(); d=top.head(12).iloc[::-1]; vals=d.priority.to_numpy(float); labels=[f"#{int(v)}" for v in d["rank"]]
    fig,ax=plt.subplots(figsize=(7.2,4.8)); bars=ax.barh(labels,vals,color=BLUE); lo=max(0,float(vals.min())-.03); ax.set_xlim(lo,1.01)
    for b,v in zip(bars,vals): ax.text(v+.002,b.get_y()+b.get_height()/2,f"{v:.3f}",va="center",fontsize=8.1)
    ax.set_title("Các khu vực có thứ tự ưu tiên cao nhất"); ax.set_xlabel("Chỉ số ưu tiên tương đối (0–1) — trục thu phóng"); ax.set_ylabel("Thứ hạng")
    save(fig,out); plt.close(fig)


def fig_agreement(df,out):
    plt=plt_setup(); x=df.thor.to_numpy(float); y=df.kh9.to_numpy(float); s=df.priority.to_numpy(float); hi=s>=np.quantile(s,.9)
    rng=np.random.default_rng(42); bg=np.where(~hi)[0]; bg=rng.choice(bg,min(5000,len(bg)),replace=False)
    fig,ax=plt.subplots(figsize=(5.9,5.2)); ax.scatter(x[bg],y[bg],s=6,alpha=.13,color=BLUE,label="Các ô còn lại"); ax.scatter(x[hi],y[hi],s=8,alpha=.27,color=BLUSH,label="Top 10% ưu tiên")
    ax.plot([0,1],[0,1],ls="--",color=MINT,lw=1.2,label="Hai nguồn cân bằng")
    ax.set(xlim=(0,1),ylim=(0,1),xlabel="Bằng chứng từ hồ sơ không kích (0–1)",ylabel="Bằng chứng từ dấu vết hố bom (0–1)",title="Mức đồng thuận giữa hai nguồn bằng chứng lịch sử")
    ax.legend(frameon=False,loc="upper center",bbox_to_anchor=(.5,-.16),ncol=3,fontsize=8.0)
    save(fig,out,bottom=.14); plt.close(fig)


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--data-dir",default="outputs_final/data"); ap.add_argument("--output-dir",default="outputs_final/figures"); args=ap.parse_args()
    data=Path(args.data_dir); out=Path(args.output_dir); out.mkdir(parents=True,exist_ok=True)
    df,labels=load_grid(data)
    top_csv=pd.read_csv(data/"priority_areas_top1000.csv")
    # e/n coordinates are encoded in cell_id and also recoverable from top-10 polygons; parse cell id for stable plotting.
    import re
    en=[]
    for cid in top_csv.cell_id.astype(str):
        m=re.search(r"_E(\d+)_N(\d+)$",cid); en.append((int(m.group(1)),int(m.group(2))) if m else (0,0))
    top=pd.DataFrame({"rank":top_csv.priority_rank_all_cells.astype(int),"priority":top_csv.priority_score_0_1,"thor":top_csv.thor_evidence_score_0_1,"kh9":top_csv.kh9_crater_evidence_score_0_1,"e":[v[0] for v in en],"n":[v[1] for v in en]})
    jobs=[
        ("01_muc_tap_trung_bang_chung.png",lambda p:fig_concentration(df,p)),
        ("02_ban_do_uu_tien.png",lambda p:fig_map(df,top,p)),
        ("03_ba_lop_thong_tin.png",lambda p:fig_sources(df,p)),
        ("04_phan_bo_muc_uu_tien.png",lambda p:fig_distribution(df,labels,p)),
        ("05_thanh_phan_diem_uu_tien.png",lambda p:fig_components(top,p)),
        ("06_top_khu_vuc_uu_tien.png",lambda p:fig_top(top,p)),
        ("07_muc_dong_thuan_nguon.png",lambda p:fig_agreement(df,p)),
    ]
    for name,fn in jobs: fn(out/name)
    print(json.dumps({"status":"PASS","figures":[n for n,_ in jobs]},ensure_ascii=False,indent=2))
if __name__=="__main__": main()
