#!/usr/bin/env python3
"""
测试语言检测功能
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.tasks.translation_task import detect_text_language

def test_language_detection():
    """测试语言检测功能"""
    
    test_cases = [
        # 英文测试
        ("Hello, this is a test text for translation.", "en"),
        ("The quick brown fox jumps over the lazy dog.", "en"),
        ("Tilly, a little fox, loved her bright red balloon. She carried it everywhere.", "en"),
        
        # 中文测试
        ("这是一个测试文本，用于翻译功能。", "zh"),
        ("你好，世界！这是中文测试。", "zh"),
        ("我们正在测试语言检测功能。", "zh"),
        
        # 日文测试
        ("こんにちは、世界！これは日本語のテストです。", "ja"),
        ("私たちは言語検出機能をテストしています。", "ja"),
        
        # 韩文测试
        ("안녕하세요, 세계! 이것은 한국어 테스트입니다.", "ko"),
        
        # 法文测试
        ("Bonjour le monde! Ceci est un test en français.", "fr"),
        ("Nous testons la fonction de détection de langue.", "fr"),
        
        # 德文测试
        ("Hallo Welt! Dies ist ein Test auf Deutsch.", "de"),
        ("Wir testen die Spracherkennungsfunktion.", "de"),
        
        # 西班牙文测试
        ("¡Hola mundo! Esta es una prueba en español.", "es"),
        ("Estamos probando la función de detección de idioma.", "es"),
        
        # 意大利文测试
        ("Ciao mondo! Questo è un test in italiano.", "it"),
        ("Stiamo testando la funzione di rilevamento della lingua.", "it"),
        
        # 混合语言测试
        ("Hello 你好 world 世界", "en"),  # 英文为主
        ("这是一个 English test 混合文本", "zh"),  # 中文为主
    ]
    
    print("语言检测测试结果:")
    print("=" * 80)
    
    correct = 0
    total = len(test_cases)
    
    for i, (text, expected) in enumerate(test_cases, 1):
        detected = detect_text_language(text)
        is_correct = detected == expected
        status = "✓" if is_correct else "✗"
        
        if is_correct:
            correct += 1
        
        print(f"{i:2d}. {status} 文本: {text[:50]}...")
        print(f"    期望: {expected}, 检测: {detected}")
        if not is_correct:
            print(f"    ❌ 检测错误!")
        print()
    
    accuracy = correct / total * 100
    print(f"总体准确率: {correct}/{total} ({accuracy:.1f}%)")
    
    return accuracy >= 80  # 80%以上认为通过


if __name__ == "__main__":
    success = test_language_detection()
    
    if success:
        print("\n✅ 语言检测测试通过!")
        sys.exit(0)
    else:
        print("\n❌ 语言检测测试失败!")
        sys.exit(1)