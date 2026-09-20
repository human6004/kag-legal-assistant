import sys

# Danh sách các thư viện cần thiết: (Tên gói cài qua pip, Tên module import trong Python)
REQUIRED_PACKAGES = [
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn"),
    ("pydantic", "pydantic"),
    ("pydantic-settings", "pydantic_settings"),
    ("python-dotenv", "dotenv"),
    ("openai", "openai"),
    ("langchain-core", "langchain_core"),
    ("langchain-community", "langchain_community"),
    ("langchain-openai", "langchain_openai"),
    ("chromadb", "chromadb"),
]

def check_dependencies():
    print("=" * 60)
    print("        KIỂM TRA THƯ VIỆN CHO HỆ THỐNG RAG")
    print("=" * 60)
    
    missing_packages = []
    
    for pip_name, import_name in REQUIRED_PACKAGES:
        try:
            mod = __import__(import_name)
            ver = getattr(mod, "__version__", "OK")
            print(f"  [✔] {pip_name:<25} -> Đã cài (v{ver})")
        except ImportError:
            print(f"  [✘] {pip_name:<25} -> CHƯA CÀI (THIẾU)")
            missing_packages.append(pip_name)
            
    print("-" * 60)
    if missing_packages:
        print(f"Phát hiện {len(missing_packages)} thư viện còn thiếu!")
        print("\nĐể cài đặt tất cả các thư viện thiếu, bạn chạy lệnh sau:")
        install_cmd = f"pip install {' '.join(missing_packages)}"
        print(f"\n   {install_cmd}\n")
    else:
        print("TUYỆT VỜI! Môi trường của bạn đã cài đầy đủ tất cả thư viện.")
    print("=" * 60)
    
    return len(missing_packages) == 0

if __name__ == "__main__":
    success = check_dependencies()
    sys.exit(0 if success else 1)
